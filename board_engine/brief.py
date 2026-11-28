"""
The design brief: what a product is and must contain, written BEFORE its boards (by the AI's planning step or by
hand) and checked against the built design by `completeness.py`.

    "brief": {
      "product_class": "building",
      "identity_features": ["steep gable roof", "front porch"],
      "detail_level": 3,
      "components": [
        {"id": "WALLS", "role": "enclosure", "count": 4},
        {"id": "ROOF", "role": "enclosure", "count": 2, "symmetric_pair": true},
        {"id": "DOOR", "role": "surface_detail", "count": 1, "parent": "WALLS"}],
      "enclosures": [{"id": "HOUSE", "components": ["WALLS", "ROOF"], "closed_sides": ["top", "left", "right", "back"],
                      "open_sides_reason": "front is the porch, shown open"}],
      "mechanisms": {"input": {"kind": "none"}, "transmission": []},
      "uncertainties": []}

Boards name the component they belong to with `"role": "<component id>"`. `validate_brief(brief)` returns
(brief, problems): the brief normalised (defaults filled) and a list of {code, severity, message}.
"""
import re

PRODUCT_CLASSES = ('building', 'vehicle_air', 'vehicle_land', 'vehicle_water', 'creature', 'furniture', 'mechanism',
                   'scene', 'other')
ROLES = ('structure', 'enclosure', 'surface_detail', 'mechanism', 'base', 'decor')
CONSTRUCTIONS = ('plain_panel', 'profiled_panel', 'ribs_on_spine', 'radial_fins', 'facets', 'layered_relief', 'gear',
                 'linkage', 'other')
SIDES = ('top', 'bottom', 'left', 'right', 'front', 'back')
INPUTS = ('hand_crank', 'motor', 'none')
VIAS = ('gear', 'rod', 'shared_axle', 'belt', 'rack')
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$')
MAX_COMPONENTS = 300


def _p(code, message, severity='error'):
    return {'code': code, 'severity': severity, 'message': message}


def validate_brief(brief):
    """-> (normalised brief or None, problems). Problems are BRIEF_INVALID errors (the brief cannot be used) or
    BRIEF_WARNING warnings (it is used as written)."""
    if not isinstance(brief, dict):
        return None, [_p('BRIEF_INVALID', '"brief" must be an object.')]
    out, probs = {}, []
    pc = brief.get('product_class', 'other')
    if pc not in PRODUCT_CLASSES:
        probs.append(_p('BRIEF_WARNING', f"brief.product_class {pc!r} is not one of {', '.join(PRODUCT_CLASSES)}; "
                                         f"using 'other'.", 'warning'))
        pc = 'other'
    out['product_class'] = pc
    feats = brief.get('identity_features') or []
    out['identity_features'] = [str(f)[:120] for f in feats if isinstance(f, (str, int, float))][:12] \
        if isinstance(feats, list) else []
    lvl = brief.get('detail_level', 3)
    out['detail_level'] = lvl if isinstance(lvl, int) and not isinstance(lvl, bool) and 1 <= lvl <= 5 else 3
    comps = brief.get('components')
    if not isinstance(comps, list) or not comps:
        return None, probs + [_p('BRIEF_INVALID', 'brief.components must list the product\'s components (at least one).')]
    if len(comps) > MAX_COMPONENTS:
        return None, probs + [_p('BRIEF_INVALID', f'brief.components lists {len(comps)} components; at most '
                                                  f'{MAX_COMPONENTS}.')]
    seen, norm = set(), []
    for k, c in enumerate(comps):
        if not isinstance(c, dict) or not isinstance(c.get('id'), str) or not ID.match(c['id']):
            probs.append(_p('BRIEF_INVALID', f'brief.components[{k}] needs an "id" (letters, digits, - _ .).'))
            continue
        if c['id'] in seen:
            probs.append(_p('BRIEF_INVALID', f"brief.components: the id {c['id']!r} is used twice."))
            continue
        seen.add(c['id'])
        n = c.get('count', 1)
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 10000:
            probs.append(_p('BRIEF_INVALID', f"brief component {c['id']!r}: count must be a whole number 1..10000."))
            continue
        role = c.get('role', 'structure')
        if role not in ROLES:
            probs.append(_p('BRIEF_WARNING', f"brief component {c['id']!r}: role {role!r} is not one of "
                                             f"{', '.join(ROLES)}; using 'structure'.", 'warning'))
            role = 'structure'
        openings = c.get('intentional_openings') or []
        norm.append({'id': c['id'], 'role': role, 'count': n, 'symmetric_pair': bool(c.get('symmetric_pair')),
                     'parent': c.get('parent') if isinstance(c.get('parent'), str) else None,
                     'construction': c.get('construction') if c.get('construction') in CONSTRUCTIONS else None,
                     'must_be_closed': bool(c.get('must_be_closed')),
                     'intentional_openings': [str(o)[:80] for o in openings][:40] if isinstance(openings, list) else []})
    for c in norm:
        if c['parent'] is not None and c['parent'] not in seen:
            probs.append(_p('BRIEF_INVALID', f"brief component {c['id']!r}: parent {c['parent']!r} is not a component."))
    out['components'] = norm
    encl = []
    for k, e in enumerate(brief.get('enclosures') or []):
        if not isinstance(e, dict) or not isinstance(e.get('id'), str):
            probs.append(_p('BRIEF_INVALID', f'brief.enclosures[{k}] needs an "id".'))
            continue
        members = [m for m in e.get('components') or [] if isinstance(m, str)]
        unknown = [m for m in members if m not in seen]
        if not members or unknown:
            probs.append(_p('BRIEF_INVALID', f"brief enclosure {e['id']!r}: components must name brief components"
                                             f"{' (unknown: ' + ', '.join(unknown) + ')' if unknown else ''}."))
            continue
        sides = e.get('closed_sides', list(SIDES))
        bad = [s for s in sides if s not in SIDES] if isinstance(sides, list) else ['?']
        if bad:
            probs.append(_p('BRIEF_INVALID', f"brief enclosure {e['id']!r}: closed_sides must be from "
                                             f"{', '.join(SIDES)}."))
            continue
        encl.append({'id': e['id'], 'components': members, 'closed_sides': list(dict.fromkeys(sides)),
                     'open_sides_reason': str(e.get('open_sides_reason') or '')[:200]})
    out['enclosures'] = encl
    mech = brief.get('mechanisms') if isinstance(brief.get('mechanisms'), dict) else {}
    inp = mech.get('input') if isinstance(mech.get('input'), dict) else {}
    kind = inp.get('kind', 'none')
    if kind not in INPUTS:
        probs.append(_p('BRIEF_WARNING', f"brief.mechanisms.input.kind {kind!r} is not one of {', '.join(INPUTS)}.",
                        'warning'))
        kind = 'none'
    trans = []
    for t in mech.get('transmission') or []:
        if isinstance(t, dict) and t.get('from') in seen and t.get('to') in seen and t.get('via', 'gear') in VIAS:
            trans.append({'from': t['from'], 'to': t['to'], 'via': t.get('via', 'gear')})
        else:
            probs.append(_p('BRIEF_WARNING', f'brief.mechanisms.transmission entry {t!r} ignored: it needs "from" and '
                                             f'"to" components and "via" one of {", ".join(VIAS)}.', 'warning'))
    out['mechanisms'] = {'input': {'kind': kind, 'component': inp.get('component') if inp.get('component') in seen
                                   else None}, 'transmission': trans}
    unc = brief.get('uncertainties') or []
    out['uncertainties'] = [str(u)[:200] for u in unc][:20] if isinstance(unc, list) else []
    if any(p['severity'] == 'error' for p in probs):
        return None, probs
    return out, probs
