"""
Firestore-backed design store (persistent, shared by every server instance).

Same interface as store.DesignStore. Uses the Firestore REST API with a Firebase service
account, so security rules can deny all browser access to these collections: designs can
only change through the server's validation pipeline.

Layout:
  board_designs/{design_id}            {name, revision, updated, components, joints, data(JSON)}
  board_designs/{design_id}/history/*  {at, actor, op, revision, detail(JSON)}

Concurrency: every mutation writes with a `currentDocument.updateTime` precondition, so two
instances editing the same design cannot overwrite each other (the loser gets Conflict).
"""
import base64
import copy
import gzip
import json
import logging
import os
import threading
import time
from urllib.parse import quote

from .model import SchemaError, check_id, normalize_design
from .store import KEEP_VERSIONS, Conflict, NotFound

log = logging.getLogger('board_engine.firestore')
SCOPES = ['https://www.googleapis.com/auth/datastore']
COLLECTION = 'board_designs'
DOC_LIMIT = 1_000_000       # bytes of design data per document (Firestore allows 1 MiB including the other fields)
COMPRESS_OVER = 900_000     # bytes: larger designs are stored gzip-compressed


def load_service_account(raw):
    """Accept the service-account JSON as plain JSON or base64 (handy for env vars)."""
    raw = raw.strip()
    if not raw.startswith('{'):
        raw = base64.b64decode(raw).decode()
    info = json.loads(raw)
    for k in ('project_id', 'client_email', 'private_key'):
        if not info.get(k):
            raise ValueError(f'service account JSON is missing {k}')
    return info


class FirestoreError(RuntimeError):
    pass


class FirestoreStore:
    backend = 'firestore'
    persistent = True

    def __init__(self, service_account=None, project_id=None, http=None):
        """`http(method, url, body=None) -> (status, json)` can be injected for tests."""
        self.project_id = project_id or (service_account or {}).get('project_id')
        if not self.project_id:
            raise ValueError('Firestore project id is required')
        self.base = (f'https://firestore.googleapis.com/v1/projects/{self.project_id}'
                     f'/databases/(default)/documents')
        self._sa = service_account
        self._creds = None
        self._token_lock = threading.Lock()
        self._http = http or self._requests_http

    # ------------------------------------------------------------------ transport
    def _token(self):
        from google.oauth2 import service_account
        import google.auth.transport.requests
        with self._token_lock:
            if self._creds is None:
                self._creds = service_account.Credentials.from_service_account_info(self._sa, scopes=SCOPES)
            if not self._creds.valid:
                self._creds.refresh(google.auth.transport.requests.Request())
            return self._creds.token

    def _requests_http(self, method, url, body=None):
        import requests
        r = requests.request(method, url, json=body, timeout=20,
                             headers={'Authorization': f'Bearer {self._token()}'})
        try:
            data = r.json() if r.content else {}
        except ValueError:
            data = {'error': {'message': r.text[:300]}}
        return r.status_code, data

    def _call(self, method, path, body=None, ok=(200,)):
        status, data = self._http(method, self.base + path, body)
        if status not in ok:
            err = (data or {}).get('error', {})
            if status == 404:
                raise NotFound(path)
            if status == 409 or err.get('status') in ('ALREADY_EXISTS', 'ABORTED'):
                raise Conflict(err.get('message', 'conflict'))
            if err.get('status') == 'FAILED_PRECONDITION':
                raise Conflict('the design was changed by another request; re-read and retry')
            raise FirestoreError(f'Firestore {method} {path}: {status} {err.get("status")} {err.get("message")}')
        return status, data

    # ------------------------------------------------------------------ encoding
    @staticmethod
    def _fields(design):
        """Document fields. A large design is stored gzip-compressed ("data_gz"), so it still fits Firestore's
        1 MiB document limit (board designs compress about 14 x); one that does not even then is refused clearly."""
        raw = json.dumps(design, separators=(',', ':')).encode()
        fields = {
            'name': {'stringValue': design.get('name') or design['id']},
            'revision': {'integerValue': str(design.get('revision', 0))},
            'updated': {'stringValue': design.get('updated') or ''},
            'components': {'integerValue': str(len(design['components']))},
            'joints': {'integerValue': str(len(design['joints']))},
        }
        if len(raw) <= COMPRESS_OVER:
            fields['data'] = {'stringValue': raw.decode()}
            return fields
        packed = base64.b64encode(gzip.compress(raw, 6)).decode()
        if len(packed) > DOC_LIMIT:
            raise SchemaError(f"design '{design['id']}' is too large for cloud storage ({len(raw) / 1e6:.1f} MB, "
                              f"{len(packed) / 1e6:.1f} MB compressed; at most {DOC_LIMIT / 1e6:.1f} MB): split it into "
                              f"several designs", 'design')
        fields['data_gz'] = {'bytesValue': packed}
        return fields

    @staticmethod
    def _design(fields):
        """The design stored in a document's fields (plain or compressed)."""
        if 'data_gz' in fields:
            return json.loads(gzip.decompress(base64.b64decode(fields['data_gz']['bytesValue'])))
        return json.loads(fields['data']['stringValue'])

    def _doc_path(self, did):
        check_id(did, 'design id')
        return f'/{COLLECTION}/{quote(did)}'

    def _read(self, did):
        _s, doc = self._call('GET', self._doc_path(did))
        return normalize_design(self._design(doc['fields'])), doc['updateTime']

    # ------------------------------------------------------------------ interface
    def exists(self, did):
        try:
            self._call('GET', self._doc_path(did) + '?mask.fieldPaths=revision')
            return True
        except NotFound:
            return False

    def list(self):
        out, token = [], None
        mask = ''.join(f'&mask.fieldPaths={f}' for f in ('name', 'revision', 'updated', 'components', 'joints'))
        while True:
            q = f'/{COLLECTION}?pageSize=300{mask}' + (f'&pageToken={quote(token)}' if token else '')
            _s, data = self._call('GET', q)
            for doc in data.get('documents', []):
                f = doc.get('fields', {})
                out.append({'id': doc['name'].rsplit('/', 1)[-1], 'name': f.get('name', {}).get('stringValue'),
                            'revision': int(f.get('revision', {}).get('integerValue', 0)),
                            'components': int(f.get('components', {}).get('integerValue', 0)),
                            'joints': int(f.get('joints', {}).get('integerValue', 0)),
                            'updated': f.get('updated', {}).get('stringValue')})
            token = data.get('nextPageToken')
            if not token:
                return sorted(out, key=lambda d: d['id'])

    def get(self, did):
        return self._read(did)[0]

    def create(self, design, actor='system', overwrite=False):
        design = normalize_design(design)
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        design['revision'] = 1
        design['created'] = design.get('created') or now
        design['updated'] = now
        if overwrite:
            self._call('PATCH', self._doc_path(design['id']), {'fields': self._fields(design)})
        else:
            self._call('POST', f'/{COLLECTION}?documentId={quote(design["id"])}', {'fields': self._fields(design)},
                       ok=(200,))
        self._snapshot(design)
        self._audit(design['id'], {'at': now, 'actor': actor, 'op': 'create', 'revision': 1})
        return design

    def delete(self, did, actor='system'):
        if not self.exists(did):
            raise NotFound(did)
        for sub in ('history', 'versions'):   # subcollections are not removed with their parent
            try:
                _s, data = self._call('GET', self._doc_path(did) + f'/{sub}?pageSize=300&mask.fieldPaths=at')
                for doc in data.get('documents', []):
                    self._call('DELETE', '/' + doc['name'].split('/documents/', 1)[1])
            except FirestoreError as e:
                log.warning('could not clear %s of %s: %s', sub, did, e)
        self._call('DELETE', self._doc_path(did))

    def mutate(self, did, fn, op, actor='system', expected_revision=None, detail=None):
        current, update_time = self._read(did)
        if expected_revision is not None and int(expected_revision) != current['revision']:
            raise Conflict(f"design '{did}' is at revision {current['revision']}, not {expected_revision}; "
                           f"re-read and retry")
        new, result = fn(copy.deepcopy(current))
        if new is None:
            return current, result, False
        new = normalize_design(new)
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        new['revision'] = current['revision'] + 1
        new['created'] = current.get('created')
        new['updated'] = now
        self._call('PATCH', self._doc_path(did) + f'?currentDocument.updateTime={quote(update_time)}',
                   {'fields': self._fields(new)})
        self._snapshot(new)
        self._audit(did, {'at': now, 'actor': actor, 'op': op, 'revision': new['revision'], 'detail': detail})
        return new, result, True

    def _snapshot(self, design):
        """Full copy of this revision (best-effort, like the history: the design itself is already saved)."""
        try:
            self._call('PATCH', self._doc_path(design['id']) + f"/versions/{design['revision']}",
                       {'fields': {'revision': {'integerValue': str(design['revision'])}, 'at': {'stringValue': design['updated']},
                                   'data': {'stringValue': json.dumps(design, separators=(',', ':'))}}})
            old = design['revision'] - KEEP_VERSIONS          # same retention as the file store
            if old >= 1:
                self._call('DELETE', self._doc_path(design['id']) + f'/versions/{old}')
        except FirestoreError as e:
            log.warning('version snapshot failed for %s: %s', design['id'], e)

    def versions(self, did):
        out, token = [], None
        while True:
            q = '/versions?pageSize=300&mask.fieldPaths=revision' + (f'&pageToken={quote(token)}' if token else '')
            _s, data = self._call('GET', self._doc_path(did) + q)
            out += [int(d['fields']['revision']['integerValue']) for d in data.get('documents', [])]
            token = data.get('nextPageToken')
            if not token:
                return sorted(out)

    def get_version(self, did, revision):
        _s, doc = self._call('GET', self._doc_path(did) + f'/versions/{int(revision)}')
        return normalize_design(self._design(doc['fields']))

    def _audit(self, did, entry):
        fields = {'seq': {'integerValue': str(time.time_ns())},  # orders entries within the same second
                  'at': {'stringValue': entry['at']}, 'actor': {'stringValue': entry['actor']},
                  'op': {'stringValue': entry['op']},
                  'revision': {'integerValue': str(entry.get('revision') or 0)},
                  'detail': {'stringValue': json.dumps(entry.get('detail'))}}
        try:
            self._call('POST', self._doc_path(did) + '/history', {'fields': fields})
        except FirestoreError as e:  # history is best-effort; the design itself is already saved
            log.warning('history write failed for %s: %s', did, e)

    def history(self, did, limit=200):
        _s, data = self._call('GET', self._doc_path(did) + f'/history?pageSize={int(limit)}&orderBy=seq%20desc')
        out = []
        for doc in data.get('documents', []):
            f = doc['fields']
            out.append({'at': f['at']['stringValue'], 'actor': f['actor']['stringValue'], 'op': f['op']['stringValue'],
                        'revision': int(f['revision']['integerValue']),
                        'detail': json.loads(f.get('detail', {}).get('stringValue', 'null'))})
        return list(reversed(out))


def store_from_env(fallback):
    """FirestoreStore when FIREBASE_SERVICE_ACCOUNT is configured, else the given file store."""
    raw = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '').strip()
    if not raw:
        return fallback
    try:
        store = FirestoreStore(load_service_account(raw))
        log.info('design storage: Firestore project %s', store.project_id)
        return store
    except Exception as e:  # never take the site down because of a bad secret
        log.error('FIREBASE_SERVICE_ACCOUNT is invalid (%s); falling back to %s storage', e, fallback.backend)
        fallback.config_error = f'FIREBASE_SERVICE_ACCOUNT is invalid: {e}'
        return fallback
