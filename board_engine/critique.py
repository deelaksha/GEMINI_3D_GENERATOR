"""
Visual critique (optional, one call per design): pictures of the compiled model are shown to a vision-capable AI with
the design brief, and it lists what a viewer would see is wrong - a missing part, a wrong count, a wrong shape or
proportion, an open surface. The list becomes problems for ONE targeted repair (repair.py); it is never a loop.

    critique_prompt(title, requirements, brief) -> text sent with the images
    parse_critique(reply) -> {'recognisable': 1..5 | None, 'discrepancies': [...]} (validated) or raises CritiqueError
    critique_problems(critique) -> diagnostics-like problems for the repair prompt
"""
import json

from .canvas import _extract, _strip_comments

ISSUES = ('missing', 'wrong_count', 'wrong_shape', 'wrong_proportion', 'open_surface', 'misplaced', 'other')
SEVERITIES = ('high', 'medium', 'low')
MAX_VIEWS = 4
MAX_VIEW_BYTES = 1_500_000      # per image, decoded


class CritiqueError(ValueError):
    pass


def critique_prompt(title, requirements='', brief=None):
    return f"""You are reviewing a flat-board (laser-cut plywood) model. The attached pictures show the compiled model from
one or more viewpoints. Compare it with what was asked for and list only what a viewer would notice is WRONG or
MISSING - not style preferences, and not the flat-board construction itself (boards, tabs and slots are expected).

Asked for: {title}
{('Requirements: ' + requirements) if requirements else ''}
{('Design brief (the agreed components and closed sides): ' + json.dumps(brief, separators=(',', ':'))) if brief else ''}

Reply with ONE JSON object and nothing else:
{{"recognisable": 1-5 (how clearly the model reads as the asked-for object),
 "discrepancies": [{{"component": "the brief component id or a short name", "issue": one of {list(ISSUES)},
                    "severity": "high"|"medium"|"low", "where": "short location", "fix": "one concrete change"}}]}}
At most 10 discrepancies, most important first. An empty list is a valid answer."""


def parse_critique(text):
    try:
        data = json.loads(_strip_comments(_extract(text or '')[0]))
    except (ValueError, RecursionError):
        raise CritiqueError('the AI reply is not a JSON object') from None
    if not isinstance(data, dict) or not isinstance(data.get('discrepancies', []), list):
        raise CritiqueError('the AI reply has no "discrepancies" list')
    rec = data.get('recognisable')
    out = {'recognisable': rec if isinstance(rec, int) and not isinstance(rec, bool) and 1 <= rec <= 5 else None,
           'discrepancies': []}
    for d in data.get('discrepancies', [])[:10]:
        if not isinstance(d, dict):
            continue
        out['discrepancies'].append({
            'component': str(d.get('component') or '')[:60], 'issue': d.get('issue') if d.get('issue') in ISSUES else 'other',
            'severity': d.get('severity') if d.get('severity') in SEVERITIES else 'medium',
            'where': str(d.get('where') or '')[:120], 'fix': str(d.get('fix') or '')[:200]})
    return out


def critique_problems(critique):
    """Problems for the repair prompt: high severity as errors (they must be fixed), the rest as warnings."""
    return [{'code': f"VISUAL_{d['issue'].upper()}", 'severity': 'error' if d['severity'] == 'high' else 'warning',
             'message': f"Visual check: {d['component'] or 'the model'} - {d['issue'].replace('_', ' ')}"
                        f"{(' (' + d['where'] + ')') if d['where'] else ''}. Suggested change: {d['fix'] or 'fix it'}."}
            for d in critique['discrepancies']]


def decode_views(views):
    """[(mime, base64 data)] from data URLs (image/png or image/jpeg), at most MAX_VIEWS, each at most MAX_VIEW_BYTES."""
    import base64
    import re
    if not isinstance(views, list) or not views or len(views) > MAX_VIEWS:
        raise CritiqueError(f'send 1 to {MAX_VIEWS} views as data URLs')
    out = []
    for v in views:
        m = re.match(r'^data:(image/(?:png|jpeg));base64,([A-Za-z0-9+/=]+)$', v or '') if isinstance(v, str) else None
        if not m:
            raise CritiqueError('each view must be a PNG or JPEG data URL')
        if len(base64.b64decode(m.group(2), validate=True)) > MAX_VIEW_BYTES:
            raise CritiqueError(f'each view must be at most {MAX_VIEW_BYTES // 1000} KB')
        out.append((m.group(1), m.group(2)))
    return out
