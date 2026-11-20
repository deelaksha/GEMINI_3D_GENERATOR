"""
Deterministic correction of joint problems (no AI involved).

A fix is derived from the intended connections (joints) — the engine never guesses intent:
  * repair   - a joined connection lost its slot fit; regenerate / resize the slot
  * rejoin   - a detached connection fits again (or only needs a safe slot repair)
  * translate- the part is off by an exact, computed offset (gap, penetration, misaligned
               slot, separated mitre); move it, then re-join if the joint was detached

Every fix is applied to a copy, the moved part must not break any of its other joined
connections, and the result is kept only if the design has no more errors than before.
Problems that need a design decision (tab landing in an intentional opening, wrong
orientation, tab off the board, ...) are reported as not auto-fixable.
"""
import copy
import logging

from .joining import apply_repair, join
from .model import build_plates, find_joint
from .operations import OperationRejected, op_translate
from .validation import TOL, evaluate_joint, validate_design

log = logging.getLogger('board_engine.autofix')


def _spec(j):
    keep = ('id', 'type', 'a', 'b', 'tab', 'slot', 'a_edge', 'b_edge')
    return {k: j[k] for k in keep if k in j}


def plan_fixes(design, tol=TOL):
    """List applicable fixes and the problems that cannot be fixed automatically."""
    plates = build_plates(design)
    fixes, unfixable = [], []
    for j in design['joints']:
        joined = j.get('status') == 'joined'
        if j['a'] not in plates or j['b'] not in plates:
            continue
        res = evaluate_joint(design, plates, j, tol)
        errors = [i for i in res['issues'] if i['severity'] == 'error']
        if joined and not errors:
            continue
        if not errors:
            fixes.append({'id': f"{j['id']}:rejoin", 'kind': 'rejoin', 'joint': j['id'],
                          'description': f"Re-join '{j['id']}' — the geometry fits again."})
            continue
        blocking = [i for i in errors if not i.get('repair')]
        if not blocking:
            fixes.append({'id': f"{j['id']}:{'repair' if joined else 'rejoin'}",
                          'kind': 'repair' if joined else 'rejoin', 'joint': j['id'],
                          'description': f"{'Regenerate' if joined else 'Re-join with'} slot repair for '{j['id']}': "
                                         + '; '.join(i['code'] for i in errors)})
            continue
        first = blocking[0]
        sug = first.get('suggestion')
        if sug and sug.get('action') == 'translate':
            fixes.append({'id': f"{j['id']}:translate", 'kind': 'translate', 'joint': j['id'],
                          'component': sug['component'], 'delta': sug['delta'], 'cause': first['code'],
                          'description': f"{first['code']}: move '{sug['component']}' by "
                                         f"[{', '.join(f'{v:g}' for v in sug['delta'])}] mm"
                                         + ('' if joined else f" and re-join '{j['id']}'")})
        else:
            unfixable.append({'joint': j['id'], 'code': first['code'], 'components': [j['a'], j['b']],
                              'message': first['message'],
                              'reason': 'needs a design decision (no safe automatic correction exists)'})
    return {'fixes': fixes, 'unfixable': unfixable}


def _errors(design):
    return validate_design(design)['summary']['errors']


def apply_fix(design, fix_id, tol=TOL):
    """Apply one planned fix. Returns (new_design, record). Raises OperationRejected."""
    plan = plan_fixes(design, tol)
    fix = next((f for f in plan['fixes'] if f['id'] == fix_id), None)
    if fix is None:
        raise OperationRejected(f"fix '{fix_id}' is not applicable to the current design (re-validate and retry)",
                                status='fix_not_applicable', extra={'available': [f['id'] for f in plan['fixes']]})
    before = _errors(design)
    work = copy.deepcopy(design)
    j = find_joint(work, fix['joint'])
    record = dict(fix)

    if fix['kind'] == 'translate':
        try:
            op_translate(work, {'id': fix['component'], 'delta': fix['delta']})
        except OperationRejected as e:
            raise OperationRejected(f"fix '{fix_id}' would break other connections of '{fix['component']}'",
                                    e.issues, status='fix_rejected', extra=e.extra)
        j = find_joint(work, fix['joint'])
    if fix['kind'] == 'repair':
        res = evaluate_joint(work, build_plates(work), j, tol)
        record['repairs'] = [apply_repair(work, i['repair']) for i in res['issues'] if i.get('repair')]
    elif j.get('status') != 'joined':
        # rejoin (possibly after the translate) through the full join pipeline
        work['joints'] = [x for x in work['joints'] if x['id'] != j['id']]
        res = join(work, _spec(j), auto_repair=True, tol=tol)
        if not res['accepted']:
            raise OperationRejected(f"fix '{fix_id}' could not re-join '{j['id']}' ({res['status']})",
                                    res['issues'], status='fix_rejected')
        work = res['design']
        record['repairs'] = res['repairs_applied']

    after = _errors(work)
    if after > before:
        raise OperationRejected(f"fix '{fix_id}' would increase errors from {before} to {after}; not applied",
                                status='fix_rejected')
    record['errors_before'], record['errors_after'] = before, after
    log.info('fix %s applied: errors %d -> %d', fix_id, before, after)
    return work, record


def auto_fix(design, max_steps=50, tol=TOL):
    """Apply planned fixes repeatedly until none apply. Returns (new_design, report)."""
    steps, skipped = [], {}
    work = design
    for _ in range(max_steps):
        plan = plan_fixes(work, tol)
        progressed = False
        skipped = {}  # a fix rejected earlier may apply once another fix has landed
        for fix in plan['fixes']:
            try:
                work, rec = apply_fix(work, fix['id'], tol)
                steps.append(rec)
                progressed = True
                break
            except OperationRejected as e:
                skipped[fix['id']] = {'fix': fix, 'reason': str(e)}
        if not progressed:
            break
    plan = plan_fixes(work, tol)
    report = validate_design(work, tol)
    return work, {'steps': steps, 'skipped': list(skipped.values()), 'unfixable': plan['unfixable'],
                  'remaining_fixes': plan['fixes'], 'valid': report['valid'], 'complete': report['complete'],
                  'summary': report['summary']}
