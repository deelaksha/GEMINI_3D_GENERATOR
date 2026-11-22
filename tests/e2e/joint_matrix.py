"""Joint validation matrix: every requested joint family, positive and negative scenarios, run on the real engine.

Positive cases go through the AI format (`board-design/v1`) like a user's design; negative cases are built in the
native format so the exact defect can be injected. Each record states the expectation BEFORE running.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from board_engine.canvas import compile_source  # noqa: E402
from board_engine.joining import join  # noqa: E402
from board_engine.model import find_component, normalize_design  # noqa: E402
from board_engine.validation import validate_design  # noqa: E402

P18 = {"name": "Plywood 18", "type": "plywood", "thickness": 18}
BASE = {"id": "BASE", "position": [0, 0, 0], "size": [300, 18, 200]}
WALL_MID = {"id": "WALL", "position": [141, 18, 20], "size": [18, 150, 160]}      # T-junction, away from edges
WALL_EDGE = {"id": "WALL", "position": [0, 18, 0], "size": [18, 150, 200]}        # corner, flush with BASE's edge


def _v1(boards, conns, joinery=None):
    d = {"format": "board-design/v1", "product": {"name": "joint test"}, "material": P18, "boards": boards, "connections": conns}
    if joinery:
        d['joinery'] = joinery
    r = compile_source(json.dumps(d))
    joints = r['design']['joints'] if r.get('design') else []
    return {'compiled': r['ok'], 'errors': sorted({x['code'] for x in r['diagnostics'] if x['severity'] == 'error'}),
            'warnings': sorted({x['code'] for x in r['diagnostics'] if x['severity'] == 'warning'}),
            'engine_types': sorted({j['type'] for j in joints if j.get('status') == 'joined'}),
            'ready': (r.get('layout') or {}).get('ready_for_production'), 'design': r.get('design')}


def _conn(t, a='WALL', b='BASE', **kw):
    return dict(id='J', type=t, board=a, into=b, **kw)


# --- native fixtures (3 mm board): 100 x 60 base, 80 x 40 wall with one 20 mm tab ------------------------------
def _base(**kw):
    c = {'id': 'BASE', 'outline': [[-50, -30], [50, -30], [50, 30], [-50, 30]],
         'placement': {'position': [0, 1.5, 0], 'rotation': [-90, 0, 0]}}
    c.update(kw)
    return c


def _wall(**kw):
    c = {'id': 'WALL', 'outline': [[-40, -20], [40, -20], [40, 20], [-40, 20]],
         'tabs': [{'id': 't1', 'edge': 0, 'offset': 40, 'width': 20, 'depth': 3}],
         'placement': {'position': [0, 23, 0], 'rotation': [0, 0, 0]}}
    c.update(kw)
    return c


def _make(*comps, joints=()):
    return normalize_design({'id': 't', 'components': list(comps), 'joints': list(joints)})


TAB = {'id': 'J1', 'type': 'tab_slot', 'a': 'WALL', 'tab': 't1', 'b': 'BASE'}


def _join(design, spec=TAB, auto_repair=True):
    res = join(design, spec, auto_repair=auto_repair)
    out = {'accepted': res['accepted'], 'status': res['status'],
           'codes': sorted({i['code'] for i in res['issues'] if i['severity'] in ('error', 'warning')})}
    if res['accepted']:
        out['design'] = res['design']
    return out


def positives():
    rows = []

    def add(name, engine, scenario, result, expect_ok=True, expect_type=None, note=''):
        ok = result['compiled'] == expect_ok and (expect_type is None or expect_type in result['engine_types'])
        rows.append({'joint': name, 'engine_type': engine, 'scenario': scenario, 'expected': 'compiles' if expect_ok else 'rejected',
                     'actual': {k: v for k, v in result.items() if k != 'design'}, 'pass': ok, 'note': note})
        return result

    add('T-joint', 'tab_slot', 'wall standing mid-base', _v1([BASE, WALL_MID], [_conn('tab_slot')]), expect_type='tab_slot')
    add('Mortise and tenon', 'tab_slot (through)', 'type "mortise_and_tenon"', _v1([BASE, WALL_MID], [_conn('mortise_and_tenon')]),
        expect_type='tab_slot', note='through tenon only; blind mortise not supported')
    add('Interlocking', 'tab_slot', 'type "interlocking"', _v1([BASE, WALL_MID], [_conn('interlocking')]), expect_type='tab_slot')
    add('Corner joint', 'finger', 'wall flush with base edge', _v1([BASE, WALL_EDGE], [_conn('finger')]), expect_type='finger')
    add('Finger joint', 'finger', 'type "finger", 5 fingers', _v1([BASE, WALL_EDGE], [_conn('finger', fingers=5)]), expect_type='finger')
    add('Dovetail joint', 'finger (substituted)', 'type "dovetail"', _v1([BASE, WALL_EDGE], [_conn('dovetail')]), expect_type='finger',
            note='SILENT SEMANTIC SUBSTITUTION: a dovetail is read as a straight finger joint (only a "normalised" warning)')
    add('Butt joint', 'edge_butt', 'glue_allowed, no fasteners', _v1([BASE, WALL_MID], [_conn('butt')], 'glue_allowed'), expect_type='edge_butt')
    add('Screw connection', 'edge_butt + screws', 'fasteners "screw"', _v1([BASE, WALL_MID], [_conn('butt', fasteners='screw')], 'glue_allowed'),
        expect_type='edge_butt')
    add('Dowel connection', 'edge_butt + dowels', 'fasteners {"kind": "dowel", "count": 3}',
        _v1([BASE, WALL_MID], [_conn('butt', fasteners={"kind": "dowel", "count": 3})], 'glue_allowed'), expect_type='edge_butt')
    add('Cross joint', 'cross_lap', 'two plates crossing', _v1([{"id": "A", "position": [0, 0, 92], "size": [200, 100, 18]},
                                                              {"id": "B", "position": [91, 0, 0], "size": [18, 100, 200]}],
                                                             [_conn('cross_lap', 'A', 'B')]), expect_type='cross_lap')
    add('Miter joint', 'edge_mitre', 'each board drawn to the other board\'s mid-plane (engine convention)',
        _v1([{"id": "TOPB", "position": [9, 132, 0], "size": [291, 18, 200]}, {"id": "SIDE", "position": [0, 0, 0], "size": [18, 141, 200]}],
            [_conn('mitre', 'SIDE', 'TOPB', edge='+y', into_edge='-x')], 'glue_allowed'), expect_type='edge_mitre')
    add('Miter joint, drawn to the outer corner', 'edge_mitre', 'boards drawn to the outside corner (how an AI draws it)',
        _v1([{"id": "TOPB", "position": [0, 132, 0], "size": [300, 18, 200]}, {"id": "SIDE", "position": [0, 0, 0], "size": [18, 150, 200]}],
            [_conn('mitre', 'SIDE', 'TOPB', edge='+y', into_edge='-x')], 'glue_allowed'), expect_ok=False,
        note='PROMPT GAP: the mid-plane convention is not in the AI prompt; this natural drawing is rejected (EDGES_NOT_COINCIDENT)')
    add('Lap joint', 'face_lap (native only)', 'type "lap" in board-design/v1', _v1([BASE, WALL_MID], [_conn('lap')]), expect_ok=False,
        note='"lap" is read as cross_lap (alias) and then fails NO_CROSSING; a face-to-face lap cannot be written in v1')
    add('Dado joint', '— (not supported)', 'type "dado"', _v1([BASE, WALL_MID], [_conn('dado')]), expect_ok=False,
        note='partial-depth housings are not modelled; must be rejected, not faked')
    add('Rabbet joint', '— (not supported)', 'type "rabbet"', _v1([BASE, WALL_EDGE], [_conn('rabbet')]), expect_ok=False)
    add('Removable connection', '— (no knock-down fittings)', 'type "cam_lock"', _v1([BASE, WALL_MID], [_conn('cam_lock')]), expect_ok=False,
        note='loose parts are covered by the support analysis ("resting"), not by joints')
    add('Hinge (moving)', 'hinge', 'overlay door on a side panel',
        _v1([{"id": "SIDE", "position": [0, 0, 0], "size": [18, 400, 300]}, {"id": "BACKP", "position": [18, 0, 0], "size": [300, 400, 18]},
             {"id": "DOOR", "position": [0, 0, 302], "size": [318, 400, 18]}],
            [_conn('finger', 'BACKP', 'SIDE'), dict(id='H', type='hinge', board='DOOR', into='SIDE', edge='-x')], 'glue_allowed'),
        expect_type='hinge')
    # tab_slot fit: slot = tab thickness + clearance, slot centred on the tab
    d = _v1([BASE, WALL_MID], [_conn('tab_slot', tabs=1)])['design']
    slot = next(f for f in find_component(d, 'BASE')['features'] if f['kind'] == 'slot')
    rows.append({'joint': 'T-joint fit', 'engine_type': 'tab_slot', 'scenario': 'slot width = wall thickness + clearance',
                 'expected': '18 + 0.10 = 18.10 mm', 'actual': {'slot_short_side': min(slot['width'], slot['height'])},
                 'pass': abs(min(slot['width'], slot['height']) - 18.1) < 1e-6})
    return rows


def negatives():
    rows = []

    def add(defect, expected_codes, actual_codes, detail):
        rows.append({'defect': defect, 'expected_any_of': expected_codes, 'actual': actual_codes, 'detail': detail,
                     'pass': bool(set(expected_codes) & set(actual_codes))})

    def val(d):
        return sorted({i['code'] for i in validate_design(d)['issues'] if i['severity'] == 'error'})

    add('Joint wider than the board', ['TAB_OUTSIDE_EDGE'],
        val(_make(_base(), _wall(tabs=[{'id': 't1', 'edge': 0, 'offset': 40, 'width': 90, 'depth': 3}]))), '90 mm tab on an 80 mm edge')
    r = _join(_make(_base(), _wall(tabs=[{'id': 't1', 'edge': 0, 'offset': 40, 'width': 20, 'depth': 6}])))
    add('Joint deeper than the material', ['TAB_PROTRUDES'],
        r['codes'] + (val(r['design']) if r.get('design') else []) + [f"accepted={r['accepted']}"],
        '6 mm tab into a 3 mm receiver (no "protrude" flag): warning, accepted')
    add('Incorrect joint orientation', ['ORIENTATION_MISMATCH'],
        _join(_make(_base(), _wall(placement={'position': [0, 23, 0], 'rotation': [-90, 0, 0]})))['codes'], 'wall lying parallel to the base')
    add('Missing mating component', ['JOINT_BROKEN'],
        sorted({i['code'] for i in validate_design(_make(_base(), _wall(),
                joints=[dict(TAB, b='NOPE', status='joined')]))['issues']}), "joint into 'NOPE' (cause: JOINT_REFERENCE_INVALID)")
    ok = _join(_make(_base(), _wall()))
    add('Duplicate joint', ['DUPLICATE_JOINT', 'JOINT_ID_EXISTS'],
        _join(ok['design'], dict(TAB, id='J2'))['codes'] if ok['accepted'] else ['first join failed'], 'same tab joined twice')
    add('Misaligned joint position', ['SLOT_MISALIGNED', 'SLOT_POSITION'],
        _join(_make(_base(features=[{'id': 's1', 'kind': 'slot', 'shape': 'rect', 'center': [4, 0], 'width': 20.1, 'height': 3.1, 'angle': 0}]),
                    _wall()))['codes'], 'existing slot 4 mm off the tab')
    add('Overlapping joints', ['TAB_OVERLAP'],
        val(_make(_base(), _wall(tabs=[{'id': 't1', 'edge': 0, 'offset': 30, 'width': 20, 'depth': 3},
                                       {'id': 't2', 'edge': 0, 'offset': 40, 'width': 20, 'depth': 3}]))), 'two tabs overlapping on one edge')
    add('Insufficient material around a joint', ['INSUFFICIENT_EDGE_MARGIN', 'SLOT_TOO_CLOSE_TO_EDGE', 'TAB_OUTSIDE_RECEIVER'],
        _join(_make(_base(), _wall(placement={'position': [0, 23, -29], 'rotation': [0, 0, 0]})))['codes'] +
        [_join(_make(_base(), _wall(placement={'position': [0, 23, -29], 'rotation': [0, 0, 0]})))['status']],
        'wall 1 mm from the base edge: the slot bridge would break')
    add('Loose joint (excess clearance)', ['SLOT_TOO_LOOSE'],
        _join(_make(_base(features=[{'id': 's1', 'kind': 'slot', 'shape': 'rect', 'center': [0, 0], 'width': 20.1, 'height': 4.0, 'angle': 0}]),
                    _wall()), auto_repair=False)['codes'], 'slot 0.9 mm wider than the tab board (auto_repair=False; with repair it is resized)')
    add('Gap at the joint', ['UNINTENDED_GAP'],
        _join(_make(_base(), _wall(placement={'position': [0, 24, 0], 'rotation': [0, 0, 0]})))['codes'], 'wall 1 mm above the base')
    add('Glued joint in a glue-free design', ['GLUE_JOINT_NOT_ALLOWED'],
        _join(_make(_base(), _wall()), {'id': 'B1', 'type': 'edge_butt', 'a': 'WALL', 'a_edge': 0, 'b': 'BASE'})['codes'], 'butt joint, joinery interlocking')
    return rows


def run():
    pos, neg = positives(), negatives()
    return {'positives': pos, 'negatives': neg,
            'summary': {'positive_pass': sum(r['pass'] for r in pos), 'positive_total': len(pos),
                        'negative_pass': sum(r['pass'] for r in neg), 'negative_total': len(neg)}}


if __name__ == '__main__':
    out = run()
    print(json.dumps(out, indent=1, default=str))
