"""FirestoreStore against an in-memory fake of the Firestore REST API (incl. preconditions)."""
import itertools
import json
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from board_engine.firestore_store import FirestoreStore, load_service_account, store_from_env
from board_engine.operations import apply_operation
from board_engine.store import Conflict, DesignStore, NotFound

from conftest import base_plate, wall


class FakeFirestore:
    """Implements the handful of Firestore REST calls FirestoreStore uses."""

    def __init__(self):
        self.docs = {}       # path -> {'fields', 'updateTime'}
        self.clock = itertools.count(1)
        self.calls = []

    def _stamp(self):
        return f'2026-01-01T00:00:{next(self.clock):06d}Z'

    def __call__(self, method, url, body=None):
        u = urlparse(url)
        path = unquote(u.path.split('/documents', 1)[1])
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.calls.append((method, path))
        parts = path.strip('/').split('/')
        if method == 'GET' and len(parts) % 2 == 0:            # document
            d = self.docs.get(path)
            return (200, {'name': 'x/documents' + path, **d}) if d else (404, {'error': {'status': 'NOT_FOUND'}})
        if method == 'GET':                                      # collection
            prefix = path + '/'
            docs = [{'name': 'x/documents' + p, **d} for p, d in sorted(self.docs.items())
                    if p.startswith(prefix) and '/' not in p[len(prefix):]]
            if q.get('orderBy', '').startswith('seq'):
                docs.sort(key=lambda d: int(d['fields']['seq']['integerValue']), reverse='desc' in q['orderBy'])
            return 200, {'documents': docs[:int(q.get('pageSize', 1000))]}
        if method == 'POST':
            doc_id = q.get('documentId') or f'auto{next(self.clock)}'
            p = f'{path}/{doc_id}'
            if p in self.docs:
                return 409, {'error': {'status': 'ALREADY_EXISTS', 'message': 'exists'}}
            self.docs[p] = {'fields': body['fields'], 'updateTime': self._stamp()}
            return 200, {'name': 'x/documents' + p, **self.docs[p]}
        if method == 'PATCH':
            pre = q.get('currentDocument.updateTime')
            if pre and self.docs.get(path, {}).get('updateTime') != pre:
                return 400, {'error': {'status': 'FAILED_PRECONDITION', 'message': 'stale'}}
            self.docs[path] = {'fields': body['fields'], 'updateTime': self._stamp()}
            return 200, self.docs[path]
        if method == 'DELETE':
            self.docs.pop(path, None)
            return 200, {}
        raise AssertionError(method)


@pytest.fixture
def fs():
    fake = FakeFirestore()
    return FirestoreStore(project_id='demo', http=fake), fake


def design(did='d1'):
    return {'id': did, 'name': 'Demo', 'components': [base_plate(), wall()]}


def test_create_get_list_delete(fs):
    store, fake = fs
    store.create(design())
    assert store.exists('d1') and not store.exists('nope')
    d = store.get('d1')
    assert d['revision'] == 1 and [c['id'] for c in d['components']] == ['BASE', 'WALL']
    assert store.list() == [{'id': 'd1', 'name': 'Demo', 'revision': 1, 'components': 2, 'joints': 0,
                             'updated': d['updated']}]
    with pytest.raises(Conflict):
        store.create(design())
    store.create(dict(design(), name='Replaced'), overwrite=True)
    assert store.get('d1')['name'] == 'Replaced'
    store.delete('d1')
    with pytest.raises(NotFound):
        store.get('d1')
    assert not any(p.startswith('/board_designs/d1') for p in fake.docs)   # history removed too


def test_mutate_persists_revision_and_history(fs):
    store, _ = fs
    store.create(design(), actor='tester')
    new, res, saved = store.mutate('d1', lambda d: (d, apply_operation(
        d, {'op': 'translate', 'id': 'WALL', 'delta': [1, 0, 0]})), 'translate', actor='tester')
    assert saved and new['revision'] == 2
    assert store.get('d1')['components'][1]['placement']['position'][0] == 1
    assert [h['op'] for h in store.history('d1')] == ['create', 'translate']
    _cur, _res, saved = store.mutate('d1', lambda d: (None, 'noop'), 'noop')
    assert not saved and store.get('d1')['revision'] == 2


def test_concurrent_writers_cannot_overwrite_each_other(fs):
    store, fake = fs
    store.create(design())

    def racing_edit(d):
        # another server instance saves while this one is still computing
        other = dict(fake.docs['/board_designs/d1'])
        fake.docs['/board_designs/d1'] = dict(other, updateTime=fake._stamp())
        return d, None
    with pytest.raises(Conflict):
        store.mutate('d1', racing_edit, 'race')
    with pytest.raises(Conflict):
        store.mutate('d1', lambda d: (d, None), 'stale', expected_revision=9)


def test_service_account_parsing_and_fallback(monkeypatch, tmp_path):
    sa = {'project_id': 'p', 'client_email': 'x@p.iam.gserviceaccount.com', 'private_key': 'k'}
    import base64
    assert load_service_account(json.dumps(sa))['project_id'] == 'p'
    assert load_service_account(base64.b64encode(json.dumps(sa).encode()).decode())['client_email'].startswith('x@')
    fallback = DesignStore(tmp_path)
    monkeypatch.delenv('FIREBASE_SERVICE_ACCOUNT', raising=False)
    assert store_from_env(fallback) is fallback
    monkeypatch.setenv('FIREBASE_SERVICE_ACCOUNT', '{"project_id": "p"}')
    st = store_from_env(fallback)
    assert st is fallback and 'missing' in st.config_error            # bad secret never crashes the site
    monkeypatch.setenv('FIREBASE_SERVICE_ACCOUNT', json.dumps(sa))
    assert isinstance(store_from_env(fallback), FirestoreStore)


def test_large_designs_are_stored_compressed_and_read_back(monkeypatch):
    import board_engine.firestore_store as fs
    from board_engine.model import SchemaError
    fake = FakeFirestore()
    st = FirestoreStore(project_id='demo', http=fake)
    d = {'id': 'big', 'name': 'Big', 'components': [base_plate()], 'joints': []}
    monkeypatch.setattr(fs, 'COMPRESS_OVER', 100)                 # treat this small design as "large"
    st.create(d)
    doc = next(v for k, v in fake.docs.items() if k.endswith('/big'))
    assert 'data_gz' in doc['fields'] and 'data' not in doc['fields']
    assert st.get('big')['components'][0]['id'] == d['components'][0]['id']
    monkeypatch.setattr(fs, 'DOC_LIMIT', 10)                       # and one that is too large even compressed
    with pytest.raises(SchemaError, match='too large for cloud storage'):
        st.create(dict(d, id='bigger'))
