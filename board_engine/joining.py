"""
Joining operation: validate -> (optionally) safely repair -> re-validate -> commit.

Rules (in order):
  1. Structurally bad requests (unknown parts, duplicate joint) are rejected.
  2. The joint is evaluated against current geometry.
  3. Any error WITHOUT a safe repair (gap, overlap, bad orientation, tab landing in an
     intentional opening, misaligned slot, ...) rejects the join with the reasons.
  4. Errors WITH a safe repair (missing slot, wrongly sized slot) are fixed only when the
     caller passes auto_repair=True; otherwise the join is rejected and the proposed
     repairs are returned so the caller can decide.
  5. Repairs are applied to a copy, the receiver's 2D profile is re-validated and the
     joint re-evaluated. A repair that creates new problems is discarded.
  6. The resulting design must not contain any error that was not there before.
  7. Only then is the joint stored with status 'joined'.

Geometry that is already correct is never modified.
"""
import copy
import logging
import time

from .model import build_plates, find_component, normalize_joint
from .validation import TOL, evaluate_joint, validate_component, validate_design

log = logging.getLogger('board_engine.joining')


def _issue_key(i):
    loc = tuple(round(v) for v in i['location']) if i.get('category') == 'assembly' and i.get('location') else None
    return (i['code'], tuple(sorted(i.get('components', []))), i.get('feature'), i.get('joint'), loc)


def apply_repair(design, repair):
    comp = find_component(design, repair['component'])
    feat = copy.deepcopy(repair['feature'])
    if repair['action'] == 'create_slot':
        existing = {f['id'] for f in comp['features']}
        base, n = feat['id'], 2
        while feat['id'] in existing:
            feat['id'] = f'{base}-{n}'
            n += 1
        comp['features'].append(feat)
    elif repair['action'] == 'resize_slot':
        comp['features'] = [feat if f['id'] == feat['id'] else f for f in comp['features']]
    else:
        raise ValueError(f"unknown repair action {repair['action']}")
    return {'action': repair['action'], 'component': comp['id'], 'feature': feat}


def check_joint(design, spec, tol=TOL):
    """Dry-run evaluation of a joint spec (nothing is modified)."""
    spec = normalize_joint(spec)
    plates = build_plates(design)
    res = evaluate_joint(design, plates, spec, tol)
    return {'joint': spec, 'ok': res['ok'], 'issues': res['issues'],
            'repairs_available': [i['repair'] for i in res['issues'] if i.get('repair')],
            'location': res.get('location')}


def join(design, spec, auto_repair=False, tol=TOL):
    """Attempt to join. Returns {'accepted': bool, 'status', 'design'?, 'joint', 'issues', ...}."""
    spec = normalize_joint(spec)
    spec.pop('status', None)
    spec.pop('repairs', None)

    def reject(status, issues, **extra):
        log.info('join %s rejected: %s (%s)', spec['id'], status, ', '.join(i['code'] for i in issues))
        return dict({'accepted': False, 'status': status, 'joint': spec, 'issues': issues}, **extra)

    if any(j['id'] == spec['id'] for j in design['joints']):
        return reject('rejected', [{'code': 'JOINT_ID_EXISTS', 'severity': 'error', 'category': 'joint',
                                    'message': f"A joint with id '{spec['id']}' already exists.",
                                    'components': [spec['a'], spec['b']], 'joint': spec['id']}])
    for j in design['joints']:
        same = (j['type'] == spec['type'] and j['a'] == spec['a'] and j['b'] == spec['b']
                and j.get('tab') == spec.get('tab') and j.get('a_edge') == spec.get('a_edge'))
        if same and j.get('status') == 'joined':
            return reject('rejected', [{'code': 'DUPLICATE_JOINT', 'severity': 'error', 'category': 'joint',
                                        'message': f"'{spec['a']}' is already joined to '{spec['b']}' by '{j['id']}'.",
                                        'components': [spec['a'], spec['b']], 'joint': spec['id']}])

    before = validate_design(design, tol)
    before_errors = {_issue_key(i) for i in before['issues'] if i['severity'] == 'error'}

    work = copy.deepcopy(design)
    plates = build_plates(work)
    res = evaluate_joint(work, plates, spec, tol)
    errors = [i for i in res['issues'] if i['severity'] == 'error']
    fixable = [i for i in errors if i.get('repair')]
    blocking = [i for i in errors if not i.get('repair')]
    if blocking:
        return reject('rejected', res['issues'])
    applied = []
    if fixable:
        if not auto_repair:
            return reject('needs_repair', res['issues'],
                          repairs_available=[i['repair'] for i in fixable])
        for i in fixable:
            applied.append(apply_repair(work, i['repair']))
        # Re-validate the modified receivers: a repair must not create new 2D problems
        for rec in {r['component'] for r in applied}:
            new_feats = {r['feature']['id'] for r in applied if r['component'] == rec}
            comp_issues = [i for i in validate_component(work, find_component(work, rec), tol)
                           if i['severity'] == 'error' and
                           (i.get('feature') in new_feats or i.get('other_feature') in new_feats)]
            if comp_issues:
                return reject('repair_unsafe', res['issues'] + comp_issues, repairs_attempted=applied)
        plates = build_plates(work)
        res = evaluate_joint(work, plates, spec, tol)
        if not res['ok']:
            return reject('rejected', res['issues'], repairs_attempted=applied)

    spec['status'] = 'joined'
    spec['joined_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    if res.get('matched_slot'):
        spec['slot'] = res['matched_slot']
    if applied:
        spec['repairs'] = applied
    work['joints'].append(spec)

    after = validate_design(work, tol)
    new_errors = [i for i in after['issues'] if i['severity'] == 'error' and _issue_key(i) not in before_errors]
    if new_errors:
        return reject('rejected_post_validation', new_errors, repairs_attempted=applied)

    log.info('join %s accepted (%s -> %s), repairs=%d', spec['id'], spec['a'], spec['b'], len(applied))
    return {'accepted': True, 'status': 'joined', 'design': work, 'joint': spec,
            'repairs_applied': applied, 'issues': res['issues'], 'validation': after}
