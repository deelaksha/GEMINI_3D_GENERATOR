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


def accept_repair(old_src, old_res, new_src, new_res):
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
    if (after['errors'], after['blocking']) >= (before['errors'], before['blocking']):
        verdict['reasons'].append(f"it is not better: {after['errors']} error(s) and {after['blocking']} production "
                                  f"problem(s) after, {before['errors']} and {before['blocking']} before")
    verdict['accepted'] = not verdict['reasons']
    return verdict
