"""
Authentication, authorisation and request limits for /api/v1.

Principals:
  * API keys (AI agents, scripts):  "Authorization: Bearer <key>"  or  "X-API-Key: <key>"
      Keys come from env BOARD_API_KEYS="key:role,key2:role" or instance/api_keys.json.
      If neither exists, one editor key is generated on first start and written to
      instance/api_keys.json (printed to the console).
  * Studio browser session: GET / sets an HttpOnly SameSite=Strict cookie. Cookie-authenticated
      requests must also send "X-Board-Client: studio" (a custom header that a cross-site page
      cannot add without a CORS grant, which this API never gives) — CSRF protection.

Roles (cumulative): viewer < editor < admin
  viewer: read, validate, dry-run checks, exports
  editor: + all design mutations (components, features, tabs, joins, batches)
  admin : + delete designs
"""
import functools
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from collections import deque

from flask import current_app, g, jsonify, request

log = logging.getLogger('board_api.auth')
ROLES = {'viewer': 1, 'editor': 2, 'admin': 3}
SESSION_COOKIE = 'board_session'
SESSION_TTL = 12 * 3600


def _session_secret(instance_dir):
    """HMAC secret for stateless session tokens, identical on every server instance.

    BOARD_SECRET should be set in production. Without it, serverless hosts (Vercel) fall back to a
    value derived from the deployment's own environment so all instances agree; locally a random
    secret is kept in the instance directory.
    """
    if os.environ.get('BOARD_SECRET'):
        return os.environ['BOARD_SECRET'].encode()
    stable = [os.environ.get(k, '') for k in ('VERCEL_PROJECT_ID', 'VERCEL_URL', 'VERCEL_GIT_COMMIT_SHA', 'VERCEL_ENV')]
    if any(stable):
        log.warning('BOARD_SECRET is not set; deriving the session secret from the deployment environment')
        return hashlib.sha256(('board-session:' + '|'.join(stable)).encode()).digest()
    path = os.path.join(instance_dir, 'session_secret')
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError:
        secret = secrets.token_bytes(32)
        try:
            with open(path, 'wb') as f:
                f.write(secret)
            os.chmod(path, 0o600)
        except OSError:
            pass
        return secret


class KeyRing:
    def __init__(self, instance_dir):
        self.keys = {}
        self._secret = _session_secret(instance_dir)
        self._lock = threading.Lock()
        self._hits = {}
        env = os.environ.get('BOARD_API_KEYS', '').strip()
        path = os.path.join(instance_dir, 'api_keys.json')
        if env:
            for item in env.split(','):
                key, _, role = item.strip().partition(':')
                if key and role in ROLES:
                    self.keys[key] = {'role': role, 'name': f'env:{key[:4]}…'}
        elif os.path.exists(path):
            with open(path) as f:
                for k in json.load(f).get('keys', []):
                    if k.get('role') in ROLES:
                        self.keys[k['key']] = {'role': k['role'], 'name': k.get('name', 'key')}
        else:
            key = 'bsk_' + secrets.token_urlsafe(24)
            self.keys[key] = {'role': 'editor', 'name': 'default-agent'}
            try:
                os.makedirs(instance_dir, exist_ok=True)
                with open(path, 'w') as f:
                    json.dump({'keys': [{'key': key, 'role': 'editor', 'name': 'default-agent'}]}, f, indent=1)
                os.chmod(path, 0o600)
                log.warning('Generated API key for AI agents (editor): %s  (stored in %s)', key, path)
            except OSError:
                log.warning('Generated a temporary API key (instance dir not writable); set BOARD_API_KEYS for agents')
        self.generated_path = path

    # Stateless signed sessions: "<expiry>.<nonce>.<hmac>" — valid on any instance sharing the secret
    def _sign(self, payload):
        return hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()

    def new_session(self):
        payload = f'{int(time.time() + SESSION_TTL)}.{secrets.token_urlsafe(16)}'
        return f'{payload}.{self._sign(payload)}'

    def session_valid(self, token):
        try:
            exp, nonce, sig = (token or '').split('.')
            return hmac.compare_digest(sig, self._sign(f'{exp}.{nonce}')) and int(exp) > time.time()
        except ValueError:
            return False

    def rate_ok(self, principal, limit, window=60.0):
        now = time.time()
        with self._lock:
            q = self._hits.setdefault(principal, deque())
            while q and q[0] < now - window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


def _error(status, code, message):
    return jsonify({'ok': False, 'error': {'status': code, 'message': message}}), status


def identify():
    ring = current_app.config['BOARD_KEYRING']
    auth = request.headers.get('Authorization', '')
    key = auth[7:].strip() if auth.lower().startswith('bearer ') else request.headers.get('X-API-Key', '').strip()
    if key:
        info = ring.keys.get(key)
        if not info:
            return None, 'invalid API key'
        return {'kind': 'api_key', 'name': info['name'], 'role': info['role'], 'id': 'key:' + info['name']}, None
    token = request.cookies.get(SESSION_COOKIE)
    if token and ring.session_valid(token):
        if request.headers.get('X-Board-Client') != 'studio':
            return None, 'cookie-authenticated requests must send X-Board-Client: studio'
        return {'kind': 'session', 'name': 'studio', 'role': 'editor', 'id': 'session:' + token.split('.')[1][:8]}, None
    return None, 'authentication required (Bearer API key or studio session)'


def require(role):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            who, err = identify()
            if not who:
                return _error(401, 'unauthenticated', err)
            if ROLES[who['role']] < ROLES[role]:
                return _error(403, 'forbidden', f"role '{who['role']}' cannot perform this action (needs '{role}')")
            ring = current_app.config['BOARD_KEYRING']
            limit = current_app.config.get('BOARD_RATE_LIMIT', 600)
            if not ring.rate_ok(who['id'], limit):
                return _error(429, 'rate_limited', f'more than {limit} requests per minute')
            g.principal = who
            return fn(*a, **kw)
        return wrapper
    return deco
