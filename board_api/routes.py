"""
/api/v1 — Board design API used by the Board Studio UI and by external AI agents.

Every state change is executed by board_engine.operations (same validation pipeline for
humans and agents). Responses use one envelope:

  success: {"ok": true, "revision": n, ...payload, "validation": {...}}
  failure: {"ok": false, "error": {"status", "message", "issues": [...] , ...}}
"""
import logging

from flask import Blueprint, Response, current_app, g, jsonify, request

from board_engine.autofix import plan_fixes
from board_engine.cutlist import cut_list
from board_engine.examples.boat import build_design as build_boat
from board_engine.examples.furniture import PRODUCTS as FURNITURE, build as build_furniture, product_params
from board_engine.manufacturing import manufacturing_report
from board_engine.joining import check_joint
from board_engine.model import SchemaError, check_id, find_component, normalize_design
from board_engine.nesting import NestingError, SHEET_PRESETS
from board_engine.operations import OperationRejected, apply_batch, apply_operation
from board_engine.store import Conflict, NotFound
from board_engine.validation import TOL, validate_design
from board_engine.views import component_view, export, model3d, production_package

from .auth import require
from .contract import CONTRACT, TOOLS

log = logging.getLogger('board_api')
bp = Blueprint('board_api', __name__, url_prefix='/api/v1')


def store():
    return current_app.config['BOARD_STORE']


def fail(status, code, message, **extra):
    return jsonify({'ok': False, 'error': dict({'status': code, 'message': message}, **extra)}), status


def body():
    data = request.get_json(silent=True)
    if data is None:
        raise SchemaError('request body must be JSON')
    if not isinstance(data, dict):
        raise SchemaError('request body must be a JSON object')
    return data


def summarize(report, full=True, design=None):
    out = {'valid': report['valid'], 'complete': report['complete'], 'summary': report['summary']}
    if full:
        out['issues'] = report['issues']
        if design is not None:
            # Attach the deterministic fix (if any) to the issues it resolves
            plan = plan_fixes(design)
            by_joint = {f['joint']: f for f in plan['fixes']}
            out['issues'] = [dict(i, fix_id=by_joint[i['joint']]['id'])
                             if i.get('joint') in by_joint and i['code'] in ('JOINT_BROKEN', 'JOINT_NOT_JOINED') else i
                             for i in report['issues']]
            out['fixes'], out['unfixable'] = plan['fixes'], plan['unfixable']
    return out


@bp.errorhandler(SchemaError)
def _schema(e):
    return fail(400, 'invalid_request', str(e), issues=[e.to_dict()])


@bp.errorhandler(NotFound)
def _nf(e):
    return fail(404, 'not_found', f'design {e} not found')


@bp.errorhandler(Conflict)
def _conflict(e):
    return fail(409, 'conflict', str(e))


@bp.errorhandler(NestingError)
def _nesting(e):
    return fail(400, 'invalid_request', str(e))


@bp.errorhandler(OperationRejected)
def _rejected(e):
    status = {'not_found': 404, 'invalid_request': 400}.get(e.status, 422)
    d = e.to_dict()
    return fail(status, d.pop('status'), d.pop('message'), **d)


def mutate(did, fn, op_name, detail=None):
    """Run fn(design) inside the store transaction, then validate and respond."""
    data = request.get_json(silent=True) or {}
    expected = data.get('expected_revision') if isinstance(data, dict) else None
    new, result, saved = store().mutate(did, fn, op_name, actor=g.principal['id'],
                                        expected_revision=expected, detail=detail)
    report = validate_design(new)
    log.info('%s %s/%s rev=%s errors=%s', g.principal['id'], did, op_name, new['revision'],
             report['summary']['errors'])
    return jsonify({'ok': True, 'revision': new['revision'], 'result': result,
                    'validation': summarize(report, design=new)})


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@bp.get('/')
def contract():
    return jsonify(CONTRACT)


@bp.get('/tools')
def tools():
    return jsonify({'tools': TOOLS})


@bp.get('/whoami')
@require('viewer')
def whoami():
    return jsonify({'ok': True, 'principal': g.principal})


@bp.get('/storage')
@require('viewer')
def storage():
    st = store()
    return jsonify({'ok': True, 'backend': st.backend, 'persistent': st.persistent,
                    'project': getattr(st, 'project_id', None), 'config_error': st.config_error
                    if hasattr(st, 'config_error') else None})


@bp.get('/sheet-presets')
def presets():
    return jsonify({'presets': {k: {'width': v[0], 'height': v[1]} for k, v in SHEET_PRESETS.items()},
                    'tolerances': TOL})


# ---------------------------------------------------------------------------
# Designs
# ---------------------------------------------------------------------------

@bp.get('/designs')
@require('viewer')
def list_designs():
    return jsonify({'ok': True, 'designs': store().list()})


@bp.post('/designs')
@require('editor')
def create_design():
    data = body()
    joints = data.pop('joints', []) or []
    design = normalize_design(dict(data, joints=[]))
    # components enter through the validated add path, joints through the join pipeline
    comps, design['components'] = design['components'], []
    work, results = apply_batch(design, [{'op': 'add_component', 'component': c} for c in comps] +
                                [{'op': 'join', 'joint': j, 'auto_repair': bool(data.get('auto_repair'))}
                                 for j in joints]) if comps or joints else (design, [])
    created = store().create(work, actor=g.principal['id'])
    report = validate_design(created)
    return jsonify({'ok': True, 'revision': created['revision'], 'design': created,
                    'validation': summarize(report)}), 201


@bp.post('/designs/examples/boat')
@require('editor')
def create_boat():
    data = request.get_json(silent=True) or {}
    did = check_id(data.get('id', 'boat'), 'id')
    params = data.get('params') or {}
    allowed = {'length', 'beam', 'depth', 'shoulder', 'lip', 'mast_height', 'thickness', 'sail_thickness'}
    if not isinstance(params, dict) or set(params) - allowed:
        raise SchemaError(f'params may contain {sorted(allowed)}', 'params')
    for k, v in params.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0.5 <= v <= 2000):
            raise SchemaError(f'params.{k} must be a number between 0.5 and 2000', f'params.{k}')
    design, failures = build_boat(did, params)
    created = store().create(design, actor=g.principal['id'], overwrite=bool(data.get('overwrite')))
    report = validate_design(created)
    return jsonify({'ok': True, 'revision': created['revision'], 'design_id': did,
                    'join_failures': [{'joint': f['joint']['id'], 'status': f['status'], 'issues': f['issues']}
                                      for f in failures],
                    'validation': summarize(report)}), 201


@bp.post('/designs/examples/furniture/<name>')
@require('editor')
def create_furniture(name):
    if name not in FURNITURE:
        return fail(404, 'not_found', f"unknown product '{name}'; choose one of {sorted(FURNITURE)}")
    data = request.get_json(silent=True) or {}
    did = check_id(data.get('id', name), 'id')
    params = data.get('params') or {}
    allowed = product_params(name)
    if not isinstance(params, dict) or set(params) - set(allowed):
        raise SchemaError(f'params may contain {sorted(allowed)}', 'params')
    for k, v in params.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0 <= v <= 5000):
            raise SchemaError(f'params.{k} must be a number between 0 and 5000', f'params.{k}')
    design, failures = build_furniture(name, did, **params)
    created = store().create(design, actor=g.principal['id'], overwrite=bool(data.get('overwrite')))
    report = validate_design(created)
    return jsonify({'ok': True, 'revision': created['revision'], 'design_id': did, 'join_failures': failures,
                    'validation': summarize(report)}), 201


@bp.get('/designs/<did>')
@require('viewer')
def get_design(did):
    d = store().get(did)
    return jsonify({'ok': True, 'revision': d['revision'], 'design': d,
                    'validation': summarize(validate_design(d), full=False)})


@bp.patch('/designs/<did>')
@require('editor')
def rename_design(did):
    data = body()
    allowed = {'name', 'description', 'expected_revision'}
    if set(data) - allowed:
        raise SchemaError(f'only {sorted(allowed - {"expected_revision"})} can be changed here', 'body')

    def fn(d):
        for k in ('name', 'description'):
            if k in data:
                if not isinstance(data[k], str) or (k == 'name' and not data[k].strip()):
                    raise SchemaError(f'{k} must be a non-empty string' if k == 'name' else f'{k} must be a string', k)
                d[k] = data[k].strip()[:200 if k == 'name' else 2000]
        return d, {k: d[k] for k in ('name', 'description')}
    return mutate(did, fn, 'rename')


@bp.post('/designs/<did>/duplicate')
@require('editor')
def duplicate_design(did):
    data = body()
    src = store().get(did)
    new_id = check_id(data.get('id'), 'id')
    copy_ = dict(src, id=new_id, name=(data.get('name') or f"{src['name']} (copy)")[:200], created=None)
    created = store().create(copy_, actor=g.principal['id'])
    return jsonify({'ok': True, 'revision': created['revision'], 'design_id': new_id,
                    'validation': summarize(validate_design(created), full=False)}), 201


@bp.delete('/designs/<did>')
@require('editor')
def delete_design(did):
    store().delete(did, actor=g.principal['id'])
    return jsonify({'ok': True, 'deleted': did})


@bp.get('/designs/<did>/history')
@require('viewer')
def history(did):
    store().get(did)
    return jsonify({'ok': True, 'history': store().history(did)})


@bp.post('/designs/<did>/validate')
@require('viewer')
def validate(did):
    d = store().get(did)
    return jsonify({'ok': True, 'revision': d['revision'], 'validation': summarize(validate_design(d), design=d)})


@bp.get('/designs/<did>/model3d')
@require('viewer')
def get_model3d(did):
    d = store().get(did)
    return jsonify(dict(model3d(d), ok=True))


@bp.put('/designs/<did>/material')
@require('editor')
def set_material(did):
    data = body()
    op = {'op': 'set_material', 'material': data.get('material', {}),
          'detach_broken_joints': bool(data.get('detach_broken_joints'))}
    return mutate(did, lambda d: (d, apply_operation(d, op)), 'set_material')


@bp.post('/designs/<did>/operations')
@require('editor')
def operations(did):
    ops = body().get('operations')

    def fn(d):
        work, results = apply_batch(d, ops)
        return work, results
    return mutate(did, fn, 'batch', detail=[o.get('op') for o in ops or [] if isinstance(o, dict)])


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

@bp.get('/designs/<did>/components')
@require('viewer')
def list_components(did):
    d = store().get(did)
    return jsonify({'ok': True, 'revision': d['revision'],
                    'components': [component_view(d, c) for c in d['components']]})


@bp.get('/designs/<did>/components/<cid>')
@require('viewer')
def get_component(did, cid):
    d = store().get(did)
    c = find_component(d, cid)
    if not c:
        return fail(404, 'not_found', f"component '{cid}' not found")
    return jsonify({'ok': True, 'revision': d['revision'], 'component': component_view(d, c)})


def _op_route(did, op, name):
    return mutate(did, lambda d: (d, apply_operation(d, op)), name,
                  detail={k: v for k, v in op.items() if k in ('id', 'feature_id', 'tab_id', 'joint_id')})


@bp.post('/designs/<did>/components')
@require('editor')
def add_component(did):
    return _op_route(did, {'op': 'add_component', 'component': body().get('component')}, 'add_component'), 201


@bp.patch('/designs/<did>/components/<cid>')
@require('editor')
def update_component(did, cid):
    data = body()
    return _op_route(did, {'op': 'update_component', 'id': cid, 'patch': data.get('patch', {}),
                           'detach_broken_joints': bool(data.get('detach_broken_joints'))}, 'update_component')


@bp.post('/designs/<did>/components/<cid>/translate')
@require('editor')
def translate(did, cid):
    data = body()
    return _op_route(did, {'op': 'translate', 'id': cid, 'delta': data.get('delta'),
                           'detach_broken_joints': bool(data.get('detach_broken_joints'))}, 'translate')


@bp.delete('/designs/<did>/components/<cid>')
@require('editor')
def delete_component(did, cid):
    return _op_route(did, {'op': 'delete_component', 'id': cid,
                           'cascade': request.args.get('cascade') in ('1', 'true')}, 'delete_component')


@bp.post('/designs/<did>/components/<cid>/features')
@require('editor')
def add_feature(did, cid):
    return _op_route(did, {'op': 'add_feature', 'id': cid, 'feature': body().get('feature')}, 'add_feature')


@bp.delete('/designs/<did>/components/<cid>/features/<fid>')
@require('editor')
def remove_feature(did, cid, fid):
    return _op_route(did, {'op': 'remove_feature', 'id': cid, 'feature_id': fid}, 'remove_feature')


@bp.post('/designs/<did>/components/<cid>/tabs')
@require('editor')
def add_tab(did, cid):
    return _op_route(did, {'op': 'add_tab', 'id': cid, 'tab': body().get('tab')}, 'add_tab')


@bp.delete('/designs/<did>/components/<cid>/tabs/<tid>')
@require('editor')
def remove_tab(did, cid, tid):
    return _op_route(did, {'op': 'remove_tab', 'id': cid, 'tab_id': tid}, 'remove_tab')


# ---------------------------------------------------------------------------
# Joints
# ---------------------------------------------------------------------------

@bp.get('/designs/<did>/joints')
@require('viewer')
def list_joints(did):
    d = store().get(did)
    return jsonify({'ok': True, 'revision': d['revision'], 'joints': d['joints']})


@bp.post('/designs/<did>/joints/check')
@require('viewer')
def check(did):
    d = store().get(did)
    res = check_joint(d, body().get('joint'))
    fits = res.pop('ok')  # envelope 'ok' means the request succeeded; 'fits' is the joint verdict
    return jsonify(dict(res, ok=True, fits=fits, revision=d['revision']))


@bp.post('/designs/<did>/joints')
@require('editor')
def create_joint(did):
    data = body()
    return _op_route(did, {'op': 'join', 'joint': data.get('joint'), 'auto_repair': bool(data.get('auto_repair'))},
                     'join'), 201


@bp.delete('/designs/<did>/joints/<jid>')
@require('editor')
def delete_joint(did, jid):
    return _op_route(did, {'op': 'unjoin', 'joint_id': jid,
                           'keep_generated_slots': request.args.get('keep_slots') in ('1', 'true')}, 'unjoin')


# ---------------------------------------------------------------------------
# Deterministic fixes (no AI): apply one, or auto-fix everything that is safely fixable
# ---------------------------------------------------------------------------

@bp.get('/designs/<did>/fixes')
@require('viewer')
def list_fixes(did):
    d = store().get(did)
    return jsonify(dict(plan_fixes(d), ok=True, revision=d['revision']))


@bp.post('/designs/<did>/fixes/apply')
@require('editor')
def apply_fix_route(did):
    fix_id = body().get('fix_id')
    if not isinstance(fix_id, str):
        raise SchemaError('fix_id is required', 'fix_id')
    return _op_route(did, {'op': 'apply_fix', 'fix_id': fix_id}, 'apply_fix')


@bp.post('/designs/<did>/fixes/auto')
@require('editor')
def auto_fix_route(did):
    data = request.get_json(silent=True) or {}
    op = {'op': 'auto_fix', 'max_steps': data.get('max_steps', 50)}

    def fn(d):
        result = apply_operation(d, op)
        return (d if result['steps'] else None), result  # nothing applied -> no new revision
    return mutate(did, fn, 'auto_fix')


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------

def _prod_opts():
    a = request.args
    opts = {}
    for k in ('preset', 'orientation', 'rotation'):
        if a.get(k):
            opts[k] = a[k]
    for k in ('width', 'height', 'margin', 'spacing', 'title_block'):
        if a.get(k):
            try:
                opts[k] = float(a[k])
            except ValueError:
                raise SchemaError(f'{k} must be a number', k)
    opts['compensate_kerf'] = a.get('kerf') in ('1', 'true')
    opts['labels'] = a.get('labels', '1') not in ('0', 'false')
    return opts


@bp.get('/designs/<did>/layout2d')
@require('viewer')
def layout2d(did):
    d = store().get(did)
    pkg = production_package(d, _prod_opts())
    return jsonify({'ok': True, 'revision': d['revision'], 'nesting': pkg['nesting'], 'cut': pkg['cut'],
                    'ready_for_production': pkg['ready_for_production'],
                    'blocking_issues': pkg['blocking_issues']})


@bp.get('/designs/<did>/manufacturing')
@require('viewer')
def manufacturing(did):
    d = store().get(did)
    report = manufacturing_report(d, compensate_kerf=request.args.get('kerf') in ('1', 'true')
                                  if request.args.get('kerf') is not None else None)
    return jsonify(dict(report, ok=True, revision=d['revision']))


@bp.get('/designs/<did>/cutlist')
@require('viewer')
def cutlist(did):
    d = store().get(did)
    return jsonify(dict(cut_list(d), ok=True, revision=d['revision']))


@bp.get('/designs/<did>/export/<fmt>')
@require('viewer')
def export_file(did, fmt):
    d = store().get(did)
    pkg = production_package(d, _prod_opts())
    if not pkg['ready_for_production'] and request.args.get('force') not in ('1', 'true'):
        return fail(409, 'not_ready_for_production',
                    'the design has blocking issues; fix them or pass force=1 to export a marked draft',
                    issues=pkg['blocking_issues'])
    sheet = request.args.get('sheet')
    try:
        payload, mime, name = export(pkg, fmt, int(sheet) - 1 if sheet else None, request.args.get('paper', 'A4'))
    except ValueError as e:
        return fail(400, 'invalid_request', str(e))
    resp = Response(payload, mimetype=mime)
    disp = 'inline' if request.args.get('inline') in ('1', 'true') else 'attachment'
    resp.headers['Content-Disposition'] = f'{disp}; filename="{name}"'
    return resp


# ---------------------------------------------------------------------------
# AI Design Canvas: project-aware prompt -> external AI -> paste JSON -> compile / save / import
# ---------------------------------------------------------------------------

def _canvas_slug(name):
    import re
    import secrets
    base = re.sub(r'[^a-z0-9]+', '-', (name or 'ai-design').lower()).strip('-')[:40] or 'ai-design'
    return f'{base}-{secrets.token_hex(2)}'


@bp.get('/canvas/spec')
def canvas_spec():
    from board_engine.canvas import CONNECTION_TYPES, FORMAT, pretty_json
    from board_engine.canvas_prompt import COMPLEX_EXAMPLE, EXAMPLE, STRUCTURES_EXAMPLE, spec_markdown
    from board_engine.manufacturing import MATERIALS
    # example_source keeps the authored key order (jsonify sorts object keys)
    return jsonify({'ok': True, 'format': FORMAT, 'markdown': spec_markdown(), 'example': EXAMPLE,
                    'example_source': pretty_json(EXAMPLE),
                    'complex_example_source': pretty_json(COMPLEX_EXAMPLE),
                    'structures_example_source': pretty_json(STRUCTURES_EXAMPLE),
                    'connection_types': list(CONNECTION_TYPES),
                    'materials': {k: {'thicknesses': v['thicknesses'], 'kerf': v['kerf']} for k, v in MATERIALS.items()}})


@bp.post('/canvas/prompt')
@require('viewer')
def canvas_prompt():
    from board_engine.canvas_prompt import build_prompt
    data = body()
    title = data.get('title')
    if not isinstance(title, str) or not title.strip():
        raise SchemaError('title is required', 'title')
    th = data.get('thickness')
    if th not in (None, '') and (isinstance(th, bool) or not isinstance(th, (int, float)) or not 0.5 <= th <= 50):
        raise SchemaError('thickness must be a number between 0.5 and 50 mm', 'thickness')
    return jsonify({'ok': True, 'prompt': build_prompt(title[:200], str(data.get('requirements') or '')[:4000],
                                                        data.get('material') or None, th or None,
                                                        data.get('joinery') or None)})


@bp.post('/canvas/compile')
@require('viewer')
def canvas_compile():
    from board_engine.canvas import compile_source
    data = body()
    res = compile_source(data.get('source'), run_production=bool(data.get('production', True)))
    if not data.get('include_design'):
        res.pop('design', None)
    # envelope 'ok' = the request worked; 'compiled' = the design compiled without errors
    return jsonify(dict(res, ok=True, compiled=res['ok']))


@bp.post('/canvas/fix')
@require('viewer')
def canvas_fix():
    from board_engine.canvas import CompileError, apply_code_fix
    data = body()
    fix = data.get('fix')
    if not isinstance(fix, dict) or not isinstance(fix.get('edits'), list):
        raise SchemaError('fix with edits is required', 'fix')
    try:
        return jsonify({'ok': True, 'source': apply_code_fix(data.get('source'), fix)})
    except (CompileError, KeyError) as e:
        return fail(422, 'fix_not_applicable', f'the fix no longer matches the code: {e}')


@bp.post('/canvas/save')
@require('editor')
def canvas_save():
    """Save the compiled design as a NEW project. Updating is only allowed for a design created by the canvas."""
    from board_engine.canvas import compile_source
    data = body()
    src = data.get('source')
    res = compile_source(src, run_production=False)
    if res.get('design') is None:
        return fail(422, 'compile_failed', 'the code does not compile; fix the errors first', issues=res['diagnostics'])
    design = res['design']
    if data.get('name'):
        design['name'] = str(data['name'])[:200]
    design['source'] = {'format': res['format'], 'code': src}
    target = data.get('design_id')
    if target:
        check_id(target, 'design_id')
        existing = store().get(target)
        if not existing.get('source'):
            return fail(409, 'not_a_canvas_design',
                        f"'{target}' was not created by the AI Design Canvas; save as a new project instead")
        design['id'] = target
        saved = store().create(design, actor=g.principal['id'], overwrite=True)
    else:
        design['id'] = _canvas_slug(design['name'])
        saved = store().create(design, actor=g.principal['id'])
    return jsonify({'ok': True, 'design_id': saved['id'], 'revision': saved['revision'],
                    'summary': res['summary'], 'diagnostics': res['diagnostics']}), 201


@bp.post('/canvas/import')
@require('editor')
def canvas_import():
    """Import selected boards (and the connections among them) into an existing design via validated operations."""
    from board_engine.canvas import compile_source
    data = body()
    target = check_id(data.get('target'), 'target')
    res = compile_source(data.get('source'), run_production=False)
    if res.get('design') is None:
        return fail(422, 'compile_failed', 'the code does not compile; fix the errors first', issues=res['diagnostics'])
    src_design = res['design']
    wanted = data.get('boards') or [c['id'] for c in src_design['components']]
    if not isinstance(wanted, list):
        raise SchemaError('boards must be a list of board ids', 'boards')
    wanted = set(wanted)
    existing = {c['id'] for c in store().get(target)['components']}
    rename = {cid: (f'AI-{cid}' if cid in existing else cid) for cid in wanted}
    keep_joints = [j for j in src_design['joints'] if j.get('status') == 'joined' and j['a'] in wanted and j['b'] in wanted]
    ops = []
    for c in src_design['components']:
        if c['id'] not in wanted:
            continue
        # keep the board's own openings / holes; slots are regenerated by the joins below
        c = dict(c, id=rename[c['id']], features=[f for f in c.get('features', []) if f.get('generated_by') is None])
        ops.append({'op': 'add_component', 'component': c})
    for j in keep_joints:
        spec = {k: v for k, v in j.items() if k not in ('status', 'repairs', 'joined_at', 'slot')}
        spec.update(a=rename[j['a']], b=rename[j['b']], id=f"AI-{j['id']}")
        ops.append({'op': 'join', 'joint': spec, 'auto_repair': True})
    if not ops:
        raise SchemaError('no boards selected', 'boards')
    return mutate(target, lambda d: apply_batch(d, ops), 'canvas_import',
                  detail={'boards': sorted(rename.values()), 'joints': len(keep_joints)})
