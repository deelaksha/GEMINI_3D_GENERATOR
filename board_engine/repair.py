"""
Deterministic acceptance of an AI repair: an AI's corrected design replaces the user's only when it is measurably
better and still the same design.

`accept_repair(old_src, old_res, new_src, new_res)` compares two compile results (from `canvas.compile_source`):
  - the reply must be a design that compiled at all (no parse error);
  - (errors, production blockers) must strictly decrease, compared in that order;
  - every board id written in the old source must still be there, unless a problem of the old compile named that
    board (the AI may remove a board it was told was wrong, never an unrelated one).
Returns {'accepted', 'reasons', 'before', 'after', 'removed', 'added'}; `reasons` explains a rejection in words the
user can act on.
"""
import json

from .canvas import _extract, _strip_comments


def _counts(res):
    """{'errors', 'blocking'} of a compile result."""
    layout = res.get('layout') or {}
    return {'errors': sum(1 for d in res['diagnostics'] if d['severity'] == 'error'),
            'blocking': layout.get('blocking_total') or len(layout.get('blocking_issues') or [])}


def source_board_ids(src):
    """Board ids as written in the source (before repeat / mirror / assemblies expand them); None if unparsable."""
    try:
        data = json.loads(_strip_comments(_extract(src)[0]))
    except (ValueError, TypeError, RecursionError):
        return None
    if not isinstance(data, dict):
        return None
    lists = [data.get('boards') or [], data.get('components') or []]
    lists += [a.get('boards') or [] for a in data.get('assemblies') or [] if isinstance(a, dict)]
    return {b['id'] for boards in lists if isinstance(boards, list) for b in boards
            if isinstance(b, dict) and isinstance(b.get('id'), str)}


def accept_repair(old_src, old_res, new_src, new_res, allow_equal=False):
    before, after = _counts(old_res), _counts(new_res)
    old_ids, new_ids = source_board_ids(old_src) or set(), source_board_ids(new_src)
    verdict = {'accepted': False, 'reasons': [], 'before': before, 'after': after, 'removed': [], 'added': []}
    if new_ids is None or new_res.get('format') is None:
        verdict['reasons'].append('the AI reply is not a design the compiler can read')
        return verdict
    named = {d.get('board') for d in old_res['diagnostics'] if d['severity'] in ('error', 'warning')}
    named |= {i for d in old_res['diagnostics'] for i in d.get('boards') or []}
    removed = sorted(old_ids - new_ids)
    verdict['removed'], verdict['added'] = removed, sorted(new_ids - old_ids)
    unexplained = [i for i in removed if i not in named]
    if unexplained:
        verdict['reasons'].append(f"the AI removed {len(unexplained)} board(s) no problem was about: "
                                  f"{', '.join(unexplained[:10])}{'…' if len(unexplained) > 10 else ''}")
    worse = (after['errors'], after['blocking']) > (before['errors'], before['blocking']) if allow_equal else \
        (after['errors'], after['blocking']) >= (before['errors'], before['blocking'])
    if worse:            # allow_equal: a fix for what a viewer saw (no compiler problem) may keep the counts
        verdict['reasons'].append(f"it is not better: {after['errors']} error(s) and {after['blocking']} production "
                                  f"problem(s) after, {before['errors']} and {before['blocking']} before")
    verdict['accepted'] = not verdict['reasons']
    return verdict


class PatchError(ValueError):
    pass


def _source_data(src):
    data = json.loads(_strip_comments(_extract(src)[0]))
    if not isinstance(data, dict):
        raise PatchError('the design is not a JSON object')
    return data


def apply_patch(source, patch):
    """The design with an AI repair patch applied: {"patch": {"boards": [...], "connections": [...], "motions": [...],
    "remove": [ids]}}. Boards / connections / motions replace the one with the same id or are added; "remove" deletes
    boards, connections and motions by id. Everything else stays as it was. Raises PatchError for a malformed patch."""
    from .canvas import pretty_json
    p = patch.get('patch', patch) if isinstance(patch, dict) else None
    if not isinstance(p, dict) or not ({'boards', 'connections', 'motions', 'remove'} & set(p)):
        raise PatchError('the reply is not a patch ({"patch": {"boards": [...], "connections": [...], "remove": [...]}})')
    data = _source_data(source)
    for key in ('boards', 'connections', 'motions'):
        items = p.get(key) or []
        if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
            raise PatchError(f'patch.{key} must be a list of objects')
        cur = data.setdefault(key, []) if items else data.get(key, [])
        where = {x.get('id'): k for k, x in enumerate(cur) if isinstance(x, dict) and isinstance(x.get('id'), str)}
        for x in items:
            if key == 'boards' and not isinstance(x.get('id'), str):
                raise PatchError('every patched board needs its "id"')
            if isinstance(x.get('id'), str) and x['id'] in where:
                cur[where[x['id']]] = x
            else:
                cur.append(x)
    gone = set(p.get('remove') or [])
    if gone:
        for key in ('boards', 'connections', 'motions'):
            if isinstance(data.get(key), list):
                data[key] = [x for x in data[key] if not (isinstance(x, dict) and x.get('id') in gone)]
    return pretty_json(data)


def neighbourhood(source, diagnostics):
    """(focus, neighbours): ids of the source boards the problems name (a generated copy "SHELF-2" counts as its source
    board "SHELF") and of the boards connected to them, from the source's connections (wildcards included)."""
    import fnmatch
    data = _source_data(source)
    ids = [b['id'] for b in data.get('boards') or [] if isinstance(b, dict) and isinstance(b.get('id'), str)]
    known = set(ids)

    def source_id(x):
        while isinstance(x, str) and x not in known and '-' in x:
            x = x.rsplit('-', 1)[0]
        return x if x in known else None
    focus = []
    for d in diagnostics:
        if d.get('severity') not in ('error', 'warning'):
            continue
        for x in [d.get('board')] + list(d.get('components') or []):
            sid = source_id(x)
            if sid and sid not in focus:
                focus.append(sid)
    match = lambda pat, i: isinstance(pat, str) and (pat == i or fnmatch.fnmatchcase(i, pat) or source_id(pat) == i)
    near = []
    for c in data.get('connections') or []:
        if not isinstance(c, dict):
            continue
        ends = [c.get('board'), c.get('into')] + list(c.get('boards') or [])
        touched = [i for i in ids if any(match(e, i) for e in ends)]
        if set(touched) & set(focus):
            near += [i for i in touched if i not in focus and i not in near]
    return focus, near
