"""
Validated design operations — the ONLY way state changes (UI, REST and AI agents alike).

Policy:
  * Component edits must leave the component's 2D cut profile valid (no errors), must not
    create an exact duplicate, and must not silently break a joined connection. If an edit
    would break joints the operation is rejected, unless the caller passes
    detach_broken_joints=true, in which case those joints are detached (status 'detached')
    and reported.
  * Joins go through joining.join (validate -> safe repair -> re-validate -> commit).
  * Design-level 3D findings (collisions, floating parts, unused slots) are reported after
    every operation but do not block work-in-progress edits.
"""
import copy

from .joining import check_joint, join
from .model import (SchemaError, build_plates, find_component, normalize_component, normalize_feature,
                    normalize_tab)
from .validation import TOL, _signature, evaluate_joint, validate_component

EDITABLE = ('name', 'group', 'description', 'outline', 'features', 'tabs', 'placement', 'thickness', 'color',
            'grain_locked')


class OperationRejected(Exception):
    def __init__(self, message, issues=None, status='rejected', extra=None):
        super().__init__(message)
        self.issues = issues or []
        self.status = status
        self.extra = extra or {}

    def to_dict(self):
        return dict({'status': self.status, 'message': str(self), 'issues': self.issues}, **self.extra)


def _check_component(design, comp, ignore_id=None):
    errs = [i for i in validate_component(design, comp, TOL) if i['severity'] == 'error']
    if errs:
        raise OperationRejected(f"component '{comp['id']}' has invalid 2D geometry", errs)
    sig = _signature(design, comp)
    for other in design['components']:
        if other['id'] in (comp['id'], ignore_id):
            continue
        if _signature(design, other) == sig:
            raise OperationRejected(f"'{comp['id']}' would be an exact duplicate of '{other['id']}'",
                                    [{'code': 'DUPLICATE_COMPONENT', 'severity': 'error', 'category': 'design',
                                      'components': [comp['id'], other['id']],
                                      'message': f"'{comp['id']}' has the same profile and placement as "
                                                 f"'{other['id']}'."}])


def _guard_joints(design, comp_id, detach):
    """Re-evaluate joined joints touching comp_id; reject or detach broken ones."""
    plates = build_plates(design)
    broken = []
    for j in design['joints']:
        if j.get('status') != 'joined' or comp_id not in (j['a'], j['b']):
            continue
        res = evaluate_joint(design, plates, j, TOL)
        errs = [i for i in res['issues'] if i['severity'] == 'error']
        if errs:
            broken.append((j, errs))
    if broken and not detach:
        raise OperationRejected(
            f"the change would break {len(broken)} joined connection(s); fix the geometry or pass "
            f"detach_broken_joints=true", [dict(e[0], joint=j['id']) for j, e in broken],
            status='would_break_joints', extra={'broken_joints': [j['id'] for j, _ in broken]})
    for j, errs in broken:
        j['status'] = 'detached'
        j['detached_reason'] = errs[0]['code']
    return [j['id'] for j, _ in broken]


def _remove_generated_slots(design, joint_ids):
    removed = []
    for c in design['components']:
        keep = []
        for f in c['features']:
            if f.get('generated_by') in joint_ids:
                removed.append({'component': c['id'], 'feature': f['id']})
            else:
                keep.append(f)
        c['features'] = keep
    return removed


def _component(design, cid):
    c = find_component(design, cid)
    if c is None:
        raise OperationRejected(f"component '{cid}' not found", status='not_found')
    return c


def op_add_component(design, op):
    comp, notes = normalize_component(op.get('component'))
    if find_component(design, comp['id']):
        raise OperationRejected(f"component id '{comp['id']}' already exists",
                                [{'code': 'DUPLICATE_COMPONENT_ID', 'severity': 'error', 'category': 'design',
                                  'components': [comp['id']], 'message': 'Component ids must be unique.'}])
    design['components'].append(comp)
    _check_component(design, comp)
    return {'component': comp, 'notes': notes}


def op_update_component(design, op):
    cid = op.get('id') or op.get('component_id')
    c = _component(design, cid)
    patch = op.get('patch') or {}
    unknown = set(patch) - set(EDITABLE)
    if unknown:
        raise SchemaError(f'cannot edit field(s): {sorted(unknown)}; editable: {list(EDITABLE)}', 'patch')
    merged = copy.deepcopy(c)
    for k, v in patch.items():
        if k == 'placement':
            merged['placement'] = dict(merged['placement'], **(v or {}))
        else:
            merged[k] = v
    new, notes = normalize_component(merged)
    if patch.get('grain_locked') is not None:
        new['grain_locked'] = bool(patch['grain_locked'])
    idx = design['components'].index(c)
    design['components'][idx] = new
    _check_component(design, new)
    detached = _guard_joints(design, cid, op.get('detach_broken_joints', False))
    return {'component': new, 'notes': notes, 'detached_joints': detached}


def op_translate(design, op):
    c = _component(design, op.get('id'))
    d = op.get('delta')
    if not isinstance(d, list) or len(d) != 3:
        raise SchemaError('delta must be [dx, dy, dz]', 'delta')
    pos = [p + float(v) for p, v in zip(c['placement']['position'], d)]
    return op_update_component(design, {'id': c['id'], 'patch': {'placement': {'position': pos}},
                                        'detach_broken_joints': op.get('detach_broken_joints', False)})


def op_delete_component(design, op):
    c = _component(design, op.get('id'))
    refs = [j['id'] for j in design['joints'] if c['id'] in (j['a'], j['b'])]
    if refs and not op.get('cascade'):
        raise OperationRejected(f"'{c['id']}' is referenced by joints {refs}; pass cascade=true to remove them",
                                status='has_dependents', extra={'joints': refs})
    design['joints'] = [j for j in design['joints'] if j['id'] not in refs]
    removed = _remove_generated_slots(design, set(refs))
    design['components'] = [x for x in design['components'] if x['id'] != c['id']]
    return {'deleted': c['id'], 'removed_joints': refs, 'removed_generated_slots': removed}


def op_add_feature(design, op):
    c = _component(design, op.get('id'))
    f = normalize_feature(op.get('feature'), 'feature')
    if any(x['id'] == f['id'] for x in c['features']):
        raise OperationRejected(f"feature '{f['id']}' already exists on '{c['id']}'")
    return op_update_component(design, {'id': c['id'], 'patch': {'features': c['features'] + [f]}})


def op_remove_feature(design, op):
    c = _component(design, op.get('id'))
    fid = op.get('feature_id')
    if not any(x['id'] == fid for x in c['features']):
        raise OperationRejected(f"feature '{fid}' not found on '{c['id']}'", status='not_found')
    users = [j['id'] for j in design['joints'] if j.get('status') == 'joined' and j['b'] == c['id']
             and j.get('slot') == fid]
    if users:
        raise OperationRejected(f"feature '{fid}' receives joint(s) {users}; unjoin first",
                                status='has_dependents', extra={'joints': users})
    return op_update_component(design, {'id': c['id'],
                                        'patch': {'features': [x for x in c['features'] if x['id'] != fid]}})


def op_add_tab(design, op):
    c = _component(design, op.get('id'))
    t = normalize_tab(op.get('tab'), 'tab')
    if any(x['id'] == t['id'] for x in c['tabs']):
        raise OperationRejected(f"tab '{t['id']}' already exists on '{c['id']}'")
    return op_update_component(design, {'id': c['id'], 'patch': {'tabs': c['tabs'] + [t]}})


def op_remove_tab(design, op):
    c = _component(design, op.get('id'))
    tid = op.get('tab_id')
    users = [j['id'] for j in design['joints'] if j['a'] == c['id'] and j.get('tab') == tid]
    if users:
        raise OperationRejected(f"tab '{tid}' is used by joint(s) {users}; unjoin first",
                                status='has_dependents', extra={'joints': users})
    return op_update_component(design, {'id': c['id'], 'patch': {'tabs': [x for x in c['tabs'] if x['id'] != tid]}})


def op_join(design, op):
    res = join(design, op.get('joint'), auto_repair=bool(op.get('auto_repair', False)))
    if not res['accepted']:
        extra = {k: res[k] for k in ('repairs_available', 'repairs_attempted') if k in res}
        extra['joint'] = res['joint']
        raise OperationRejected(f"join '{res['joint']['id']}' {res['status']}", res['issues'],
                                status=res['status'], extra=extra)
    design.clear()
    design.update(res['design'])
    return {'joint': res['joint'], 'repairs_applied': res['repairs_applied'],
            'warnings': [i for i in res['issues'] if i['severity'] == 'warning']}


def op_unjoin(design, op):
    jid = op.get('joint_id')
    if not any(j['id'] == jid for j in design['joints']):
        raise OperationRejected(f"joint '{jid}' not found", status='not_found')
    design['joints'] = [j for j in design['joints'] if j['id'] != jid]
    removed = [] if op.get('keep_generated_slots') else _remove_generated_slots(design, {jid})
    return {'removed_joint': jid, 'removed_generated_slots': removed}


def op_set_material(design, op):
    mat = op.get('material') or {}
    allowed = {'name', 'thickness', 'kerf', 'clearance', 'color'}
    if set(mat) - allowed:
        raise SchemaError(f'material fields: {sorted(allowed)}', 'material')
    design['material'] = dict(design['material'], **mat)
    from .model import normalize_design
    design.update(normalize_design(design))
    # Thickness changes affect every tab/slot fit: re-check all joined connections
    broken = []
    for c in design['components']:
        try:
            broken += _guard_joints(design, c['id'], op.get('detach_broken_joints', False))
        except OperationRejected as e:
            raise OperationRejected('material change breaks joined connections', e.issues, e.status, e.extra)
    return {'material': design['material'], 'detached_joints': sorted(set(broken))}


OPERATIONS = {
    'add_component': op_add_component, 'update_component': op_update_component, 'translate': op_translate,
    'delete_component': op_delete_component, 'add_feature': op_add_feature, 'remove_feature': op_remove_feature,
    'add_tab': op_add_tab, 'remove_tab': op_remove_tab, 'join': op_join, 'unjoin': op_unjoin,
    'set_material': op_set_material,
}
READ_ONLY_OPS = {'check_joint'}


def apply_operation(design, op):
    if not isinstance(op, dict) or op.get('op') not in OPERATIONS:
        raise SchemaError(f"op must be one of {sorted(OPERATIONS)}", 'op')
    return OPERATIONS[op['op']](design, op)


def apply_batch(design, ops):
    """Apply operations in order on a copy; all-or-nothing."""
    if not isinstance(ops, list) or not ops or len(ops) > 200:
        raise SchemaError('operations must be a non-empty list of <= 200 items', 'operations')
    work = copy.deepcopy(design)
    results = []
    for i, op in enumerate(ops):
        try:
            results.append({'index': i, 'op': op.get('op'), 'result': apply_operation(work, op)})
        except OperationRejected as e:
            e.extra = dict(e.extra, failed_index=i, failed_op=op.get('op'))
            raise
        except SchemaError as e:
            raise OperationRejected(f'operation {i}: {e}', [e.to_dict()], status='invalid_request',
                                    extra={'failed_index': i})
    return work, results


__all__ = ['apply_operation', 'apply_batch', 'check_joint', 'OperationRejected', 'OPERATIONS']
