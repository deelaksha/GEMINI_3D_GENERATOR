"""
/api/v1 — Board design API used by the Board Studio UI and by external AI agents.

Every state change is executed by board_engine.operations (same validation pipeline for
humans and agents). Responses use one envelope:

  success: {"ok": true, "revision": n, ...payload, "validation": {...}}
  failure: {"ok": false, "error": {"status", "message", "issues": [...] , ...}}
"""
import functools
import os
import threading
import json
import logging
import time

try:
    import fcntl
except ImportError:          # Windows: one process only (the development server)
    fcntl = None

from werkzeug.exceptions import HTTPException
from flask import Blueprint, Response, current_app, g, jsonify, request

from board_engine.autofix import plan_fixes
from board_engine.cutlist import cut_list
from board_engine.deadline import TimeBudgetExceeded, time_budget
from board_engine.examples.boat import build_design as build_boat
from board_engine.examples.furniture import PRODUCTS as FURNITURE, build as build_furniture, product_params
from board_engine.manufacturing import MATERIALS, PROCESSES, manufacturing_report
from board_engine.joining import check_joint
from board_engine.model import SchemaError, check_id, find_component, normalize_design
from board_engine.nesting import NestingError, SHEET_PRESETS
from board_engine.operations import OperationRejected, apply_batch, apply_operation, import_boards
from board_engine.store import Conflict, NotFound
from board_engine.validation import TOL, validate_design
from board_engine.views import component_view, export, model3d, production_package

from .auth import may_change, require
from .contract import CONTRACT, TOOLS

log = logging.getLogger('board_api')
bp = Blueprint('board_api', __name__, url_prefix='/api/v1')


def store():
    return current_app.config['BOARD_STORE']


def fail(status, code, message, **extra):
    return jsonify({'ok': False, 'error': dict({'status': code, 'message': message}, **extra)}), status


def budget():
    """Seconds a request may spend in geometry checks (validation, nesting, compile) before it is stopped."""
    return current_app.config.get('BOARD_TIME_BUDGET', 90)


def board_cap():
    """Most boards one compile may expand to for the caller: anonymous browser sessions and API keys get a cap (a
    237-byte "repeat" can describe 20,000 boards); admins only the engine's global limit."""
    who = getattr(g, 'principal', None) or {}
    if who.get('role') == 'admin':
        return None
    if who.get('kind') == 'api_key':
        return current_app.config.get('BOARD_MAX_BOARDS_KEY', 20000)
    return current_app.config.get('BOARD_MAX_BOARDS_SESSION', 10000)


_SLOTS, _SLOTS_LOCK = {}, threading.Lock()


def _take_slot():
    """Reserve one of this user's concurrent compile slots (BOARD_COMPILE_SLOTS, default 2); None when all are in use.
    A compile may legitimately run for minutes, so one session must not start many of them at once."""
    who = g.principal['id']
    with _SLOTS_LOCK:
        if _SLOTS.get(who, 0) >= current_app.config.get('BOARD_COMPILE_SLOTS', 2):
            return None
        if sum(_SLOTS.values()) >= current_app.config.get('BOARD_COMPILE_TOTAL', 8):
            return False                 # the whole process is full (a new session per request must not get around it)
        _SLOTS[who] = _SLOTS.get(who, 0) + 1
    return who


def _give_slot(who):
    with _SLOTS_LOCK:
        _SLOTS[who] = _SLOTS.get(who, 1) - 1
        if _SLOTS[who] <= 0:
            del _SLOTS[who]


def _busy(server_full=False):
    if server_full:
        resp, status = fail(503, 'server_busy', 'the server is compiling as many designs as it can right now; try again '
                            'in a minute')
        resp.headers['Retry-After'] = '30'
        return resp, status
    return fail(429, 'busy', f"{current_app.config.get('BOARD_COMPILE_SLOTS', 2)} compiles of yours are already running; "
                'wait for one to finish (or cancel it) and try again')


def heavy(fn):
    """Routes that compile a design: at most BOARD_COMPILE_SLOTS at a time per user."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        who = _take_slot()
        if not who:
            return _busy(server_full=who is False)
        try:
            return fn(*a, **kw)
        finally:
            _give_slot(who)
    return wrapper


_AI_LOCK = threading.Lock()
AI_LEDGER = 'ai_quota.json'      # in the instance dir: {who: [times of paid AI calls], '*': everyone's (one day)}


def _ai_who():
    """Whom a paid AI call is counted against: an API key by its principal; a browser by its address, because a new
    session cookie costs nothing (behind a proxy, TRUST_PROXY makes request.remote_addr the client's address)."""
    who = g.principal
    return who['id'] if who['kind'] == 'api_key' else f'ip:{request.remote_addr or "unknown"}'


def _ai_quota(charge):
    """None when one more paid AI call is allowed - recorded at once when `charge` - else the 429 response. At most
    BOARD_AI_PER_HOUR per user and BOARD_AI_PER_DAY in all. The counts live in one file in the instance directory,
    read and written under an exclusive lock, so every gunicorn worker process shares them."""
    now, who = time.time(), _ai_who()
    per_hour = current_app.config.get('BOARD_AI_PER_HOUR', 20)
    per_day = current_app.config.get('BOARD_AI_PER_DAY', 300)
    folder = current_app.config.get('BOARD_INSTANCE_DIR') or current_app.instance_path
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, AI_LEDGER)
    with _AI_LOCK, open(path + '.lock', 'a') as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)              # released when the file closes
        try:
            with open(path) as f:
                calls = json.load(f)
        except (OSError, ValueError):
            calls = {}
        calls = {k: [t for t in v if t > now - (86400 if k == '*' else 3600)]
                 for k, v in calls.items() if isinstance(v, list)}
        if len(calls.get('*', ())) >= per_day:
            return fail(429, 'ai_daily_limit', f'the server has made its {per_day} AI calls for today; copy the '
                        f'prompt into your own AI instead, or try again tomorrow')
        if len(calls.get(who, ())) >= per_hour:
            return fail(429, 'ai_hourly_limit', f'at most {per_hour} AI calls per hour; copy the prompt into your '
                        f'own AI instead, or try again later')
        if charge:
            calls.setdefault(who, []).append(now)
            calls.setdefault('*', []).append(now)
            tmp = f'{path}.{os.getpid()}.{threading.get_ident()}.tmp'
            with open(tmp, 'w') as f:
                json.dump({k: v for k, v in calls.items() if v}, f)
            os.replace(tmp, path)
    return None


def ai_quota(fn):
    """Paid AI routes: refused at once when the caller's AI quota is used up. Nothing is charged here - the route
    charges `_ai_quota(charge=True)` right before it really calls the provider, so a request that is rejected as busy
    or invalid, or that needs no AI (ai-fix of a design the safe fixes repair), costs nothing."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        return _ai_quota(charge=False) or fn(*a, **kw)
    return wrapper


def size_budget(boards):
    """Seconds for the work that follows a compile (production files, an import), grown with the compiled design's
    real board count the way the compiler's own budget is - counted after repeat / mirror / instances are expanded,
    so a design that places one module thousands of times is not cut off midway."""
    from board_engine.canvas import BUDGET_BOARDS, MAX_BUDGET
    return max(budget(), min(MAX_BUDGET, budget() * boards / BUDGET_BOARDS))


def budgeted(fn):
    """Read-only heavy endpoints: stop with 503 instead of running on (nothing is written by these routes)."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        with time_budget(budget()):
            return fn(*a, **kw)
    return wrapper


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


@bp.errorhandler(Exception)
def _unexpected(e):
    """Any other failure in the API answers JSON (never an HTML error page); HTTP errors keep their status."""
    if isinstance(e, HTTPException):
        return fail(e.code or 500, (e.name or 'error').lower().replace(' ', '_'), e.description or e.name)
    log.exception('unexpected error in %s', request.path)
    return fail(500, 'internal_error', f'internal error ({type(e).__name__}); the request was not completed')


@bp.get('/healthz')
def healthz():
    """Liveness / readiness for a load balancer: the process answers and the design store is reachable."""
    try:
        current_app.config['BOARD_STORE'].exists('healthz-probe')
        return jsonify({'ok': True})
    except Exception as e:  # noqa: BLE001 - report, never raise
        return jsonify({'ok': False, 'error': f'design store unavailable ({type(e).__name__})'}), 503


@bp.errorhandler(TimeBudgetExceeded)
def _timeout(e):
    return fail(503, 'time_budget_exceeded', f'{e}; split the design into smaller parts or retry')


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


class Forbidden(Exception):
    """The principal may not change this design (auth.may_change)."""


@bp.errorhandler(Forbidden)
def _forbidden(e):
    return fail(403, 'forbidden', str(e))


def check_may_change(design, delete=False):
    """Raise Forbidden unless the current principal may change (or delete) `design` - see auth.py Ownership."""
    why = may_change(g.principal, design, delete)
    if why:
        raise Forbidden(why)


def owned(design):
    """A new design (or copy) belongs to the principal creating it, whatever the request body says."""
    design['owner'] = g.principal['id']
    return design


@bp.errorhandler(OperationRejected)
def _rejected(e):
    status = {'not_found': 404, 'invalid_request': 400}.get(e.status, 422)
    d = e.to_dict()
    return fail(status, d.pop('status'), d.pop('message'), **d)


def mutate(did, fn, op_name, detail=None):
    """Run fn(design) inside the store transaction, then validate and respond."""
    data = request.get_json(silent=True) or {}
    expected = data.get('expected_revision') if isinstance(data, dict) else None

    def guarded(d):                     # checked inside the store's transaction, on the revision being changed
        check_may_change(d)
        return fn(d)
    new, result, saved = store().mutate(did, guarded, op_name, actor=g.principal['id'],
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
    created = store().create(owned(work), actor=g.principal['id'])
    report = validate_design(created)
    return jsonify({'ok': True, 'revision': created['revision'], 'design': created,
                    'validation': summarize(report)}), 201


def _may_overwrite(did, data):
    """Replacing an existing design (`overwrite`) is a change of that design."""
    if data.get('overwrite') and store().exists(did):
        check_may_change(store().get(did))


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
    _may_overwrite(did, data)
    created = store().create(owned(design), actor=g.principal['id'], overwrite=bool(data.get('overwrite')))
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
    _may_overwrite(did, data)
    created = store().create(owned(design), actor=g.principal['id'], overwrite=bool(data.get('overwrite')))
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


@bp.get('/designs/<did>/versions')
@require('viewer')
def list_versions(did):
    store().get(did)
    return jsonify({'ok': True, 'design_id': did, 'versions': store().versions(did)})


@bp.get('/designs/<did>/versions/<int:rev>')
@require('viewer')
def get_version(did, rev):
    return jsonify({'ok': True, 'design': store().get_version(did, rev)})


@bp.post('/designs/<did>/restore')
@require('editor')
def restore_version(did):
    """Make an earlier revision current again. Non-destructive: it is saved as a NEW revision."""
    rev = body().get('revision')
    if isinstance(rev, bool) or not isinstance(rev, int):
        raise SchemaError('revision must be an integer', 'revision')
    old = store().get_version(did, rev)
    return mutate(did, lambda d: (dict(old, id=did), {'restored_revision': rev}), 'restore', detail={'revision': rev})


@bp.post('/designs/<did>/duplicate')
@require('editor')
def duplicate_design(did):
    data = body()
    src = store().get(did)
    new_id = check_id(data.get('id'), 'id')
    copy_ = dict(src, id=new_id, name=(data.get('name') or f"{src['name']} (copy)")[:200], created=None)
    created = store().create(owned(copy_), actor=g.principal['id'])
    return jsonify({'ok': True, 'revision': created['revision'], 'design_id': new_id,
                    'validation': summarize(validate_design(created), full=False)}), 201


@bp.delete('/designs/<did>')
@require('editor')
def delete_design(did):
    """Owner or admin only (auth.py Ownership)."""
    check_may_change(store().get(did), delete=True)
    store().delete(did, actor=g.principal['id'])
    return jsonify({'ok': True, 'deleted': did})


@bp.get('/designs/<did>/history')
@require('viewer')
def history(did):
    store().get(did)
    return jsonify({'ok': True, 'history': store().history(did)})


@bp.post('/designs/<did>/validate')
@require('viewer')
@budgeted
def validate(did):
    d = store().get(did)
    return jsonify({'ok': True, 'revision': d['revision'], 'validation': summarize(validate_design(d), design=d)})


@bp.get('/designs/<did>/model3d')
@require('viewer')
@budgeted
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
@budgeted
def layout2d(did):
    d = store().get(did)
    pkg = production_package(d, _prod_opts())
    return jsonify({'ok': True, 'revision': d['revision'], 'nesting': pkg['nesting'], 'cut': pkg['cut'],
                    'ready_for_production': pkg['ready_for_production'],
                    'blocking_issues': pkg['blocking_issues']})


@bp.get('/designs/<did>/manufacturing')
@require('viewer')
@budgeted
def manufacturing(did):
    d = store().get(did)
    report = manufacturing_report(d, compensate_kerf=request.args.get('kerf') in ('1', 'true')
                                  if request.args.get('kerf') is not None else None)
    return jsonify(dict(report, ok=True, revision=d['revision']))


@bp.get('/designs/<did>/cutlist')
@require('viewer')
@budgeted
def cutlist(did):
    d = store().get(did)
    return jsonify(dict(cut_list(d), ok=True, revision=d['revision']))


@bp.get('/designs/<did>/export/<fmt>')
@require('viewer')
@budgeted
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

def _machine(data):
    """The cutting machine the canvas user set up ({'kerf': mm, 'sheet': {'width', 'height'}}), or None.
    Without kerf and sheet (laser support switched off) only the switches are kept, e.g. {'coloring': True}.
    Optional `process` ('laser' | 'router' | 'saw') and `tool_diameter` (router bit, mm): with a sheet but no kerf,
    the kerf is the process's own (0.15 mm laser, the bit diameter for a router)."""
    from board_engine.manufacturing import PROCESSES, machine_process
    m = data.get('machine')
    if m is None:
        return None
    proc = None
    if isinstance(m, dict) and ('process' in m or 'tool_diameter' in m):
        if m.get('process') is None:
            raise SchemaError(f'machine.process must be one of {list(PROCESSES)}', 'machine.process')
        try:
            proc = machine_process(m)
        except ValueError as e:
            raise SchemaError(str(e), 'machine.tool_diameter' if 'tool_diameter' in str(e) else 'machine.process')
        if 'kerf' not in m and 'sheet' in m:
            kerf = proc.get('tool_diameter') or PROCESSES[proc['process']]['kerf']
            m = dict(m, **({'kerf': kerf} if kerf else {}))
    if isinstance(m, dict) and 'kerf' not in m and 'sheet' not in m:
        return {**{k: True for k in ('coloring', 'file') if m.get(k)}, **(proc or {})} or None
    sheet = m.get('sheet') if isinstance(m, dict) else None
    ok = lambda v, lo, hi: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi
    kmax = 25 if proc and proc['process'] == 'router' else 5       # a router's kerf is its bit (up to 25 mm)
    if not (isinstance(m, dict) and ok(m.get('kerf'), 0.01, kmax) and isinstance(sheet, dict)
            and ok(sheet.get('width'), 50, 5000) and ok(sheet.get('height'), 50, 5000)):
        raise SchemaError(f'machine must be {{"kerf": 0.01..{kmax} mm, "sheet": {{"width": 50..5000, "height": '
                          f'50..5000 mm}}}}', 'machine')
    out = {'kerf': float(m['kerf']), 'sheet': {'width': float(sheet['width']), 'height': float(sheet['height'])}}
    for k, lo, hi in (('measured', 0.5, 50), ('fit', -0.5, 1),           # optional: real board thickness, slot fit,
                      ('cut_speed', 0.1, 1000), ('engrave_speed', 0.1, 5000), ('sheet_price', 0, 1e6)):   # job report
        if m.get(k) is not None:
            if not ok(m[k], lo, hi):
                raise SchemaError(f'machine.{k} must be between {lo} and {hi} mm', f'machine.{k}')
            out[k] = float(m[k])
    for k in ('shared_edges', 'coloring', 'color_sheets', 'file'):    # optional switches (file: AI delivers a .json file)
        if m.get(k):
            out[k] = True
    return {**out, **(proc or {})}


def _canvas_slug(name):
    import re
    import secrets
    base = re.sub(r'[^a-z0-9]+', '-', (name or 'ai-design').lower()).strip('-')[:40] or 'ai-design'
    return f'{base}-{secrets.token_hex(2)}'


CANVAS_EXAMPLES = {'home': 'my_home.json'}       # larger examples, fetched only when picked in the editor


@bp.get('/canvas/examples/<name>')
def canvas_example(name):
    """Source of a larger example design (board_engine/examples/<file>), loaded on demand by the editor."""
    import os
    from board_engine.canvas import pretty_json
    if name not in CANVAS_EXAMPLES:
        return fail(404, 'not_found', f'no example {name!r}; available: {", ".join(CANVAS_EXAMPLES)}')
    path = os.path.join(os.path.dirname(build_boat.__code__.co_filename), CANVAS_EXAMPLES[name])
    with open(path) as f:
        return jsonify({'ok': True, 'name': name, 'source': pretty_json(json.load(f))})


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
    title, images = data.get('title'), bool(data.get('images'))
    if not images and (not isinstance(title, str) or not title.strip()):
        raise SchemaError('title is required (or attach reference images)', 'title')
    title = title if isinstance(title, str) else ''
    th = data.get('thickness')
    if th not in (None, '') and (isinstance(th, bool) or not isinstance(th, (int, float)) or not 0.5 <= th <= 50):
        raise SchemaError('thickness must be a number between 0.5 and 50 mm', 'thickness')
    return jsonify({'ok': True, 'prompt': build_prompt(title[:200], str(data.get('requirements') or '')[:4000],
                                                        data.get('material') or None, th or None,
                                                        data.get('joinery') or None, _machine(data), images,
                                                        brief=_brief_of(data))})


@bp.post('/canvas/repair-prompt')
@require('viewer')
@heavy
def canvas_repair_prompt():
    """Follow-up prompt that hands this source's diagnostics back to the external AI for a minimal correction."""
    from board_engine.canvas import compile_source
    from board_engine.canvas_prompt import build_repair_prompt
    data = body()
    src = data.get('source')
    machine, requirements = _machine(data), _requirements(data)
    res = compile_source(src, run_production=True, time_budget=budget(), machine=machine, requirements=requirements,
                         max_boards=board_cap())
    prompt = build_repair_prompt(src, res['diagnostics'], _with_total(res.get('layout') or {}), machine,
                                 requirements=requirements)
    return jsonify({'ok': True, 'compiled': res['ok'], 'prompt': prompt,
                    'problems': prompt.count('\n- [')})


@bp.post('/canvas/integer-fix-prompt')
@require('viewer')
@heavy
def canvas_integer_fix_prompt():
    """Follow-up prompt asking the external AI to update only the floating-point dimensions to clean integers."""
    import json
    from board_engine.canvas import compile_source, find_non_integer_dimensions
    from board_engine.canvas_prompt import build_integer_fix_prompt
    src = body().get('source')
    res = compile_source(src, run_production=False, time_budget=budget(), max_boards=board_cap())
    data = res.get('design') or {}
    raw_json = None
    try:
        raw_json = json.loads(src) if src else {}
    except Exception:
        raw_json = data
    issues = find_non_integer_dimensions(raw_json if raw_json else data)
    prompt = build_integer_fix_prompt(src, issues)
    return jsonify({
        'ok': True,
        'count': len(issues),
        'issues': issues,
        'prompt': prompt
    })


@bp.post('/canvas/update-prompt')
@require('viewer')
@heavy
def canvas_update_prompt():
    """Follow-up prompt asking the external AI to change only what a change request affects."""
    from board_engine.canvas import compile_source
    from board_engine.canvas_prompt import build_update_prompt
    data = body()
    change, images = data.get('change'), bool(data.get('images'))
    if not images and (not isinstance(change, str) or not change.strip()):
        raise SchemaError('change (the requested modification) is required', 'change')
    change = change if isinstance(change, str) else ''
    machine = _machine(data)
    res = compile_source(data.get('source'), run_production=False, time_budget=budget(), max_boards=board_cap(),
                         machine=machine)
    if res.get('format') is None:
        return fail(422, 'compile_failed', 'the current code is not a design yet; generate it first', issues=res['diagnostics'])
    return jsonify({'ok': True, 'prompt': build_update_prompt(data.get('source'), change[:4000], res['diagnostics'], machine,
                                                               images)})


def _with_total(layout):
    """The production blockers sent with a result (at most 50), plus one line saying how many more there are."""
    blocking = list(layout.get('blocking_issues') or [])
    more = (layout.get('blocking_total') or len(blocking)) - len(blocking)
    if more > 0:
        blocking.append({'code': 'MORE_PRODUCTION_PROBLEMS', 'severity': 'error',
                         'message': f'{more} more production problem(s) of the kinds listed above were not listed; fix '
                                    f'every part they apply to the same way.'})
    return blocking


def _with_repair_prompt(res, source, machine=None):
    """Attach the follow-up fix prompt for a compile that found errors or warnings, built from this result (no
    second compile), so "Copy fix prompt" copies it at once."""
    from board_engine.canvas_prompt import build_repair_prompt
    layout = res.get('layout') or {}
    blocking = _with_total(layout)
    if any(d['severity'] in ('error', 'warning') for d in res['diagnostics']) or blocking:
        res['repair_prompt'] = build_repair_prompt(source, res['diagnostics'], blocking, machine)
        res['repair_problems'] = res['repair_prompt'].count('\n- [')
    return res


def _requirements(data):
    """The free-text requirements sent with a compile (sizes stated there are checked against the design)."""
    r = data.get('requirements')
    return r[:4000] if isinstance(r, str) and r.strip() else None


@bp.post('/canvas/compile')
@require('viewer')
@heavy
def canvas_compile():
    from board_engine.canvas import compile_source
    data = body()
    res = compile_source(data.get('source'), run_production=bool(data.get('production', True)), time_budget=budget(),
                         machine=_machine(data), requirements=_requirements(data), max_boards=board_cap())
    if data.get('repair_prompt'):
        _with_repair_prompt(res, data.get('source'), _machine(data))
    if not data.get('include_design'):
        res.pop('design', None)
    # envelope 'ok' = the request worked; 'compiled' = the design compiled without errors
    return jsonify(dict(res, ok=True, compiled=res['ok']))


COMPILE_STAGES = ('parse', 'geometry', 'joints', 'dimensions', 'joint_validation', 'collisions', 'model')


@bp.post('/canvas/compile-stream')
@require('viewer')
def canvas_compile_stream():
    """Same compile as /canvas/compile, streamed as NDJSON: {"type":"progress",...} lines at real stage boundaries,
    then one {"type":"result",...} line. If the client disconnects, the compile is cancelled at the next progress point.
    Progress lines may carry `board` / `a`, `b` (the boards being worked on), `joins` (the joint order, once) and
    `preview` (the boards' outlines and placement matrices, once, after geometry generation) for the live animation."""
    import json
    import queue
    import threading
    import time
    from board_engine.canvas import compile_source
    from board_engine.progress import CompileCancelled, reporting
    data = body()
    source, production, seconds = data.get('source'), bool(data.get('production', True)), budget()
    cap = board_cap()                   # read here: the compile runs in its own thread, outside the request
    include_design, want_prompt, machine = bool(data.get('include_design')), bool(data.get('repair_prompt')), _machine(data)
    requirements = _requirements(data)
    events, cancelled = queue.Queue(), threading.Event()
    slot = _take_slot()
    if not slot:
        return _busy(server_full=slot is False)
    state = {'stage': -1, 'sent': 0.0}
    t0 = time.monotonic()

    def reporter(stage, done, total, info):
        if cancelled.is_set():
            raise CompileCancelled()
        idx = COMPILE_STAGES.index(stage)
        if idx < state['stage']:
            return                      # nested work reporting an earlier stage: keep the stream monotonic
        now = time.monotonic()
        finished = done is not None and done >= total
        if idx == state['stage'] and not finished and now - state['sent'] < 0.05 and not info.keys() & {'preview', 'joins'}:
            return                      # throttle inner-loop updates to ~20/s (the one-off preview / joint list always go)
        state['stage'], state['sent'] = idx, now
        events.put(dict(info, type='progress', stage=stage, done=done, total=total, t=round(now - t0, 3)))

    def work():
        try:
            with reporting(reporter):
                res = compile_source(source, run_production=production, time_budget=seconds, machine=machine,
                                     requirements=requirements, max_boards=cap)
            if want_prompt:
                _with_repair_prompt(res, source, machine)
            if not include_design:
                res.pop('design', None)
            events.put({'type': 'result', 'result': dict(res, ok=True, compiled=res['ok']), 't': round(time.monotonic() - t0, 3)})
        except CompileCancelled:
            log.info('canvas compile cancelled by the client')
        except BaseException as e:      # never leave the stream hanging
            log.exception('canvas compile stream failed')
            events.put({'type': 'error', 'message': f'Internal compiler error: {type(e).__name__}'})
        finally:
            _give_slot(slot)            # the compile (or its cancellation) is over
            events.put(None)

    # started here, not when the response is first read: if the client is gone before that, the compile still ends
    # (within its budget) and its finally gives the compile slot back
    threading.Thread(target=work, daemon=True, name='canvas-compile').start()

    def stream():
        try:
            while True:
                try:
                    ev = events.get(timeout=1.0)
                except queue.Empty:
                    yield '{"type":"heartbeat"}\n'      # also how a disconnected client is noticed
                    continue
                if ev is None:
                    return
                yield json.dumps(ev, separators=(',', ':')) + '\n'
        finally:
            cancelled.set()

    return Response(stream(), mimetype='application/x-ndjson', headers={'X-Accel-Buffering': 'no'})


@bp.post('/canvas/export')
@require('viewer')
@heavy
def canvas_export():
    """Everything a cutting machine needs, in one zip: per sheet an SVG (laser) and a DXF (CNC / CAD), the PDF booklet
    and a README with material, kerf, sheet size, colour / layer map and cut order. Kerf-compensated, 1:1 in mm.
    Refused while the design has blocking issues unless `force` (then every file name is marked DRAFT)."""
    import io
    import zipfile
    from board_engine.canvas import compile_source
    from board_engine.cutpaths import LEGEND, sheet_print_svg
    from board_engine.jobreport import job_lines, job_report
    from board_engine.lightburn import sheet_lbrn2
    from board_engine.painting import painting_guide, painting_lines
    data = body()
    machine = _machine(data)
    res = compile_source(data.get('source'), run_production=False, time_budget=budget(), max_boards=board_cap(),
                         machine=machine)
    design = res.get('design')
    if not design or not design['components']:
        return fail(422, 'compile_failed', 'the design does not compile yet; fix its errors first', issues=res['diagnostics'])
    with time_budget(size_budget(len(design['components']))):
        pkg = production_package(design, {'compensate_kerf': True, 'labels': data.get('labels', True) is not False})
    # the production checks only see the part of the design that compiled, so compile errors block production too
    blocking = [d for d in res['diagnostics'] if d['severity'] == 'error'] + pkg['blocking_issues']
    draft = bool(blocking)
    if draft and not data.get('force'):
        return fail(409, 'not_ready_for_production', 'the design has blocking issues; fix them or download a marked draft',
                    issues=blocking[:50])
    n, mat, cut = pkg['nesting'], design['material'], pkg['cut']
    slug = _canvas_slug(design['name']).rsplit('-', 1)[0]
    prefix = f"{'DRAFT-' if draft else ''}{slug}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for i in range(n['sheet_count']):
            for fmt in ('svg', 'dxf'):
                z.writestr(f"{prefix}-sheet{i + 1}.{fmt}", export(pkg, fmt, i)[0])
            z.writestr(f"{prefix}-sheet{i + 1}.lbrn2", sheet_lbrn2(design, n, cut, i, machine, labels=data.get('labels', True) is not False))
            for face in ('front', 'back'):          # printed decals (colouring on): artwork aligned with the cut sheet
                art = sheet_print_svg(design, n, cut, i, face)
                if art:
                    z.writestr(f"{prefix}-sheet{i + 1}-print-{face}.svg", art)
        z.writestr(f'{prefix}-booklet.pdf', export(pkg, 'pdf', None, data.get('paper') or 'A4')[0])
        from board_engine.testfit import test_fit_files
        z.writestr(f'{prefix}-test-fit.svg', test_fit_files((machine or {}).get('measured') or mat['thickness'], mat['kerf'])['svg'])
        parts = len(n['placements'])
        z.writestr(f'{prefix}-README.txt', '\n'.join([
            f"{design['name']} - machine files{'  (DRAFT: NOT READY FOR PRODUCTION)' if draft else ''}",
            '',
            f"Material   : {mat.get('name')} ({mat['type']}), {mat['thickness']:g} mm thick",
            *([f"Machine    : {PROCESSES[machine.get('process') or 'laser']['label']}, "
               f"{machine['sheet']['width']:g} x {machine['sheet']['height']:g} mm bed, "
               f"{machine['kerf']:g} mm kerf"] if machine and 'kerf' in machine else []),
            f"Sheets     : {n['sheet_count']} x {n['sheet']['width']:g} x {n['sheet']['height']:g} mm, {parts} parts",
            f"Units      : millimetres, scale 1:1 - import / print at 100 %, never 'fit to page'",
            f"Kerf       : paths already compensated for a {cut['kerf_compensation']:g} mm kerf "
            f"(set the machine's own kerf / tool offset to 0)",
            f"Layers     : {LEGEND}",
            'Cut order  : per sheet - engrave / pocket first, then every inner cut, then the outlines',
            f"Slots      : {mat['thickness']:g} mm board + {mat['clearance']:g} mm clearance. Cut *-test-fit.svg first: push the "
            'tab into each slot and enter the snuggest value that goes in by hand as "Slot fit" in the laser settings',
            'Files      : *-sheetN.lbrn2 LightBurn projects (layers set: engrave, labels, inner cuts, outlines - check the '
            'power once for your laser), *-sheetN.svg for any laser software (colour-mapped hairlines, raster images), '
            '*-sheetN.dxf (R12) for CNC / CAD, *-booklet.pdf for assembly',
            *job_lines(job_report(n, cut, machine)),
            *(painting_lines(painting_guide(design)) if design.get('coloring') else []),
            *(['', 'Blocking issues:'] + [f"- {i['message']}" for i in blocking[:30]] if draft else []),
            '']))
    resp = Response(buf.getvalue(), mimetype='application/zip')
    resp.headers['Content-Disposition'] = f'attachment; filename="{prefix}-cut-files.zip"'
    return resp


def _ai_reply_source(text):
    """The design JSON out of an AI reply (a fenced block or the outermost {...}); the raw text if there is none."""
    from board_engine.canvas import _extract
    body, _off = _extract(text)
    return body.strip() or text


@bp.get('/canvas/ai-status')
@require('viewer')
def canvas_ai_status():
    from board_engine.ai_client import provider
    name, model = provider()
    return jsonify({'ok': True, 'provider': name, 'model': model})


def _brief_of(data):
    """The request's validated design brief (None without one); a brief that cannot be used is a 400."""
    if data.get('brief') in (None, ''):
        return None
    from board_engine.brief import validate_brief
    brief, probs = validate_brief(data['brief'])
    if brief is None:
        raise SchemaError('; '.join(p['message'] for p in probs if p['severity'] == 'error')[:500], 'brief')
    return brief


def _brief_reply(text):
    """The brief out of an AI reply: (brief, problems) or (None, problems)."""
    import json
    from board_engine.brief import validate_brief
    from board_engine.canvas import _extract, _strip_comments
    try:
        raw = json.loads(_strip_comments(_extract(text)[0]))
    except (ValueError, RecursionError):
        return None, [{'code': 'BRIEF_INVALID', 'severity': 'error', 'message': 'the AI reply is not a JSON object'}]
    return validate_brief(raw.get('brief', raw) if isinstance(raw, dict) else raw)


@bp.post('/canvas/brief-prompt')
@require('viewer')
def canvas_brief_prompt():
    """The planning prompt (step 1): the AI writes the design brief before any board."""
    from board_engine.canvas_prompt import build_brief_prompt
    data = body()
    title, images = data.get('title'), bool(data.get('images'))
    if not images and (not isinstance(title, str) or not title.strip()):
        raise SchemaError('title is required (or attach reference images)', 'title')
    return jsonify({'ok': True, 'prompt': build_brief_prompt(str(title or '')[:200], str(data.get('requirements') or '')[:4000],
                                                              images)})


@bp.post('/canvas/brief-check')
@require('viewer')
def canvas_brief_check():
    """Validate a design brief (pasted from an AI chat or edited by hand): the normalised brief and its problems."""
    from board_engine.brief import validate_brief
    data = body()
    raw = data.get('brief')
    if isinstance(raw, str):
        brief, probs = _brief_reply(raw)
    else:
        brief, probs = validate_brief(raw)
    return jsonify({'ok': True, 'valid': brief is not None, 'brief': brief, 'problems': probs})


@bp.post('/canvas/ai-brief')
@require('editor')
@ai_quota
@heavy
def canvas_ai_brief():
    """Ask the configured AI for the design brief (the planning step); it is validated before it is returned."""
    from board_engine.ai_client import AIError, complete, provider
    from board_engine.canvas_prompt import build_brief_prompt
    data = body()
    title = data.get('title')
    if not isinstance(title, str) or not title.strip():
        raise SchemaError('title is required', 'title')
    prompt = build_brief_prompt(title[:200], str(data.get('requirements') or '')[:4000], False, transport='server')
    over = _ai_quota(charge=True)
    if over:
        return over
    try:
        reply = complete(prompt)
    except AIError as e:
        return fail(502, 'ai_failed', str(e))
    brief, probs = _brief_reply(reply)
    if brief is None:
        return fail(502, 'ai_failed', 'the AI did not return a usable design brief: '
                                      + '; '.join(p['message'] for p in probs)[:300])
    return jsonify({'ok': True, 'brief': brief, 'problems': probs, 'provider': provider()[0]})


@bp.post('/canvas/ai-generate')
@require('editor')
@ai_quota
@heavy
def canvas_ai_generate():
    """Generate a design with the configured AI from the canvas's description (the same prompt as step 2)."""
    from board_engine.ai_client import AIError, complete, provider
    from board_engine.canvas_prompt import build_prompt
    data = body()
    title = data.get('title')
    if not isinstance(title, str) or not title.strip():
        raise SchemaError('title is required', 'title')
    th = data.get('thickness')
    if th not in (None, '') and (isinstance(th, bool) or not isinstance(th, (int, float)) or not 0.5 <= th <= 50):
        raise SchemaError('thickness must be a number between 0.5 and 50 mm', 'thickness')
    material, joinery = data.get('material') or None, data.get('joinery') or 'interlocking'
    if material is not None and material not in MATERIALS:
        raise SchemaError(f"material must be one of {', '.join(MATERIALS)}", 'material')
    if joinery not in ('interlocking', 'glue_allowed'):
        raise SchemaError('joinery must be interlocking or glue_allowed', 'joinery')
    brief = _brief_of(data)
    prompt = build_prompt(title[:200], str(data.get('requirements') or '')[:4000], material, th or None, joinery,
                          _machine(data), transport='server', brief=brief)
    over = _ai_quota(charge=True)
    if over:
        return over
    try:
        reply = complete(prompt)
    except AIError as e:
        return fail(502, 'ai_failed', str(e))
    source = _ai_reply_source(reply)
    if brief:                                   # the approved plan travels with the design, so it is checked
        source = _with_brief(source, brief)
    return jsonify({'ok': True, 'source': source, 'provider': provider()[0]})


def _with_brief(source, brief):
    """The design source with the approved brief in it (the AI may leave it out); unchanged if it is not JSON."""
    import json
    from board_engine.canvas import pretty_json
    try:
        data = json.loads(source)
    except ValueError:
        return source
    if not isinstance(data, dict) or data.get('brief'):
        return source
    return pretty_json({**({'format': data['format']} if 'format' in data else {}), 'brief': brief,
                        **{k: v for k, v in data.items() if k != 'format'}})


@bp.post('/canvas/ai-fix')
@require('editor')
@ai_quota
@heavy
def canvas_ai_fix():
    """Fix the code's problems: first every safe (unambiguous) fix the compiler offers, then - only if errors remain -
    one AI round. The AI's reply is compiled and replaces the code only when it is better and keeps the design's
    boards (`repair.accept_repair`); otherwise the code is returned as it was, with the reasons."""
    from board_engine.ai_client import AIError, complete, provider
    from board_engine.canvas import CompileError, apply_code_fix, compile_source
    from board_engine.canvas_prompt import build_patch_repair_prompt
    from board_engine.repair import accept_repair
    data = body()
    src = data.get('source')
    machine, requirements = _machine(data), _requirements(data)
    cap = board_cap()
    compile_ = lambda s, production: compile_source(s, run_production=production, time_budget=budget(), machine=machine,
                                                    requirements=requirements, max_boards=cap)
    cur = src
    for _ in range(SAFE_FIX_ROUNDS):            # free and deterministic: never pay the AI for what the compiler can fix
        fix = next((f for d in compile_(cur, False)['diagnostics'] if d['severity'] == 'error'
                    for f in d.get('fixes') or [] if f.get('safe')), None)
        if fix is None:
            break
        try:
            cur = apply_code_fix(cur, fix)
        except (CompileError, KeyError):
            break
    res = compile_(cur, True)
    errors = [d for d in res['diagnostics'] if d['severity'] == 'error']
    blocking = _with_total(res.get('layout') or {})
    visual = _visual_problems(data.get('visual'))          # what the AI's visual check saw (one round)
    if not errors and not blocking and not visual:
        return jsonify({'ok': True, 'source': cur, 'problems': 0, 'changed': cur != src, 'accepted': True, 'reasons': []})
    prompt = build_patch_repair_prompt(cur, res['diagnostics'] + visual, blocking, machine, requirements=requirements)
    over = _ai_quota(charge=True)                # only now is the AI really called
    if over:
        return over
    try:
        reply = complete(prompt)
    except AIError as e:
        return fail(502, 'ai_failed', str(e))
    candidate, why = _repair_candidate(cur, reply)
    verdict = accept_repair(cur, res, candidate, compile_(candidate, True), allow_equal=bool(visual) and not errors)
    if why:
        verdict['accepted'], verdict['reasons'] = False, [why] + verdict['reasons']
    out = candidate if verdict['accepted'] else cur
    return jsonify(dict(verdict, ok=True, source=out, candidate=None if verdict['accepted'] else candidate,
                        problems=prompt.count('\n- ['), changed=out != src, provider=provider()[0]))


SAFE_FIX_ROUNDS = 10

def _visual_problems(raw):
    """Validated problems from an AI visual check (critique.critique_problems), at most 10; [] without them."""
    if not isinstance(raw, list):
        return []
    return [{'code': p['code'], 'severity': 'error' if p.get('severity') == 'error' else 'warning',
             'message': str(p['message'])[:400]} for p in raw[:10]
            if isinstance(p, dict) and isinstance(p.get('code'), str) and p['code'].startswith('VISUAL_')
            and isinstance(p.get('message'), str)]


@bp.post('/canvas/ai-critique')
@require('editor')
@ai_quota
@heavy
def canvas_ai_critique():
    """The optional visual check: views of the compiled model (data URLs captured in the browser) are shown to the
    AI with the design brief; it lists what looks missing or wrong. One paid call; the problems it returns can be
    sent to /canvas/ai-fix as "visual" for one targeted repair."""
    import json
    from board_engine.ai_client import AIError, complete, provider
    from board_engine.critique import CritiqueError, critique_problems, critique_prompt, decode_views, parse_critique
    data = body()
    try:
        views = decode_views(data.get('views'))
    except CritiqueError as e:
        raise SchemaError(str(e), 'views')
    brief = None
    try:
        brief = (json.loads(data.get('source') or '{}') or {}).get('brief')
    except (ValueError, AttributeError):
        pass
    prompt = critique_prompt(str(data.get('title') or 'the product')[:200], str(data.get('requirements') or '')[:2000],
                             brief if isinstance(brief, dict) else None)
    over = _ai_quota(charge=True)
    if over:
        return over
    try:
        reply = complete(prompt, images=views)
    except AIError as e:
        return fail(502, 'ai_failed', str(e))
    try:
        crit = parse_critique(reply)
    except CritiqueError as e:
        return fail(502, 'ai_failed', f'the AI visual check did not answer as asked: {e}')
    return jsonify({'ok': True, 'critique': crit, 'problems': critique_problems(crit), 'provider': provider()[0]})

def _repair_candidate(current, reply):
    """(the repaired design source, a reason it cannot be used or None) from the AI's reply: a patch is applied to the
    current design (repair.apply_patch); a complete design is taken as it is."""
    import json
    from board_engine.repair import PatchError, apply_patch
    text = _ai_reply_source(reply)
    try:
        obj = json.loads(text)
    except ValueError:
        return text, None
    if isinstance(obj, dict) and 'patch' in obj:
        try:
            return apply_patch(current, obj), None
        except (PatchError, ValueError) as e:
            return current, f'the AI patch could not be applied: {e}'
    return text, None


@bp.post('/canvas/resize')
@require('viewer')
def canvas_resize():
    """New overall length / height / depth for a design: board thicknesses stay, the space between them stretches."""
    from board_engine.canvas import parse_source, pretty_json
    from board_engine.resize import ResizeError, resize_design
    data = body()
    target = {}
    for k in ('length', 'height', 'depth'):
        v = data.get(k)
        if v is not None:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 10 <= v <= 5000:
                raise SchemaError(f'{k} must be between 10 and 5000 mm', k)
            target[k] = float(v)
    parsed, _src, _off, diags = parse_source(data.get('source'))
    if parsed is None:
        return fail(422, 'compile_failed', 'the code is not valid JSON yet; compile and fix it first', issues=diags)
    try:
        new, ext = resize_design(parsed, target)
    except (ResizeError, KeyError, TypeError, IndexError) as e:
        return fail(422, 'resize_failed', str(e) if isinstance(e, ResizeError) else f'the design cannot be resized: {e}')
    return jsonify({'ok': True, 'source': pretty_json(new), 'overall': ext})


@bp.post('/canvas/test-fit')
@require('viewer')
def canvas_test_fit():
    """The test-fit comb + tab for the laser (SVG or DXF): slots of measured thickness + -0.1..+0.3 mm."""
    from board_engine.testfit import test_fit_files
    data = body()
    machine = _machine(data) or {}
    machine.setdefault('kerf', 0.15)
    t = data.get('thickness')
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not 0.5 <= t <= 50:
        raise SchemaError('thickness (the measured board thickness) must be between 0.5 and 50 mm', 'thickness')
    fmt = data.get('format', 'svg')
    if fmt not in ('svg', 'dxf'):
        raise SchemaError('format must be svg or dxf', 'format')
    files = test_fit_files(float(t), machine['kerf'])
    resp = Response(files[fmt], mimetype='image/svg+xml' if fmt == 'svg' else 'application/dxf')
    resp.headers['Content-Disposition'] = f'attachment; filename="test-fit-{t:g}mm.{fmt}"'
    return resp


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
@heavy
def canvas_save():
    """Save the compiled design as a NEW project. Updating is only allowed for a design created by the canvas."""
    from board_engine.canvas import compile_source
    data = body()
    src = data.get('source')
    res = compile_source(src, run_production=False, time_budget=budget(), max_boards=board_cap(),
                         machine=_machine(data))
    if res.get('design') is None or res.get('partial'):
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
        check_may_change(existing)
        design['id'] = target

        def update(d):
            check_may_change(d)                     # again inside the transaction
            return dict(design, created=d.get('created')), None
        saved, _r, _w = store().mutate(target, update, 'canvas_update', actor=g.principal['id'])
    else:
        design['id'] = _canvas_slug(design['name'])
        saved = store().create(owned(design), actor=g.principal['id'])
    return jsonify({'ok': True, 'design_id': saved['id'], 'revision': saved['revision'],
                    'summary': res['summary'], 'diagnostics': res['diagnostics']}), 201


@bp.post('/canvas/import')
@require('editor')
@heavy
def canvas_import():
    """Import selected boards (and the connections among them) into an existing design via validated operations."""
    from board_engine.canvas import compile_source
    data = body()
    target = check_id(data.get('target'), 'target')
    res = compile_source(data.get('source'), run_production=False, time_budget=budget(), max_boards=board_cap())
    if res.get('design') is None or res.get('partial'):
        return fail(422, 'compile_failed', 'the code does not compile; fix the errors first', issues=res['diagnostics'])
    src_design = res['design']
    wanted = data.get('boards') or [c['id'] for c in src_design['components']]
    if not isinstance(wanted, list):
        raise SchemaError('boards must be a list of board ids', 'boards')
    wanted = set(wanted)
    existing = {c['id'] for c in store().get(target)['components']}
    rename = {cid: (f'AI-{cid}' if cid in existing else cid) for cid in wanted}
    keep_joints = [j for j in src_design['joints'] if j.get('status') == 'joined' and j['a'] in wanted and j['b'] in wanted]
    # keep each board's own openings / holes; slots are regenerated by the joins
    comps = [dict(c, id=rename[c['id']], features=[f for f in c.get('features', []) if f.get('generated_by') is None])
             for c in src_design['components'] if c['id'] in wanted]
    specs = []
    for j in keep_joints:
        spec = {k: v for k, v in j.items() if k not in ('status', 'repairs', 'joined_at', 'slot')}
        spec.update(a=rename[j['a']], b=rename[j['b']], id=f"AI-{j['id']}")
        specs.append(spec)
    if not comps:
        raise SchemaError('no boards selected', 'boards')
    # moving parts come along when all their boards (and the board they are mounted on) are imported
    moves = []
    for m in src_design.get('motions') or []:
        if all(b in wanted for b in m['boards']) and m['on'] in wanted:
            nm = dict(m, boards=[rename[b] for b in m['boards']], on=rename[m['on']])
            if m.get('axle'):
                nm['axle'] = dict(m['axle'], boards=[rename[b] for b in m['axle'].get('boards', []) if b in rename])
            moves.append(nm)

    def run(d):
        results = import_boards(d, comps, specs)      # any number of boards: validated once, not per operation
        if moves:
            taken = {m['id'] for m in d.get('motions') or []}
            d['motions'] = list(d.get('motions') or []) + [
                dict(m, id=f"AI-{m['id']}" if m['id'] in taken else m['id']) for m in moves]
        return d, results
    with time_budget(size_budget(len(src_design['components']))):
        return mutate(target, run, 'canvas_import',
                      detail={'boards': sorted(rename.values()), 'joints': len(keep_joints), 'motions': len(moves)})
