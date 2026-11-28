"""
File-backed design store: one JSON document per design + an append-only history log.

Every mutation goes through DesignStore.mutate(), which:
  * loads the latest revision under a per-design lock,
  * rejects stale writes when the caller supplies expected_revision,
  * runs the mutation on a deep copy (callers validate inside it),
  * bumps the revision, writes atomically and records an audit entry.
"""
import contextlib
import copy
import json
import os
import shutil
import threading
import time
from pathlib import Path

try:
    import fcntl
except ImportError:          # Windows: one process only (the development server)
    fcntl = None

from .model import check_id, normalize_design


class NotFound(KeyError):
    pass


class Conflict(RuntimeError):
    pass


KEEP_VERSIONS = 100     # full snapshots kept per design (older ones are pruned; the audit history stays)


def with_owner(design, owner):
    """`design` with its creator's principal id kept as `owner` (normalize_design does not carry it; see auth.may_change).
    Without one the design is unowned."""
    if owner:
        design['owner'] = owner
    return design


class DesignStore:
    backend = 'file'
    persistent = True      # False when the server had to fall back to a temp directory
    config_error = None

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks = {}
        self._depth = {}
        self._guard = threading.Lock()

    @contextlib.contextmanager
    def _lock(self, did):
        """One writer per design: a thread lock inside this process plus a file lock across processes (several
        gunicorn workers share the folder), so two saves can never both build on the same revision."""
        with self._guard:
            lock = self._locks.setdefault(did, threading.RLock())
        with lock:
            depth = self._depth.get(did, 0)
            self._depth[did] = depth + 1
            held = None
            try:
                if depth == 0 and fcntl:                 # outermost only: flock is not re-entrant across opens
                    check_id(did, 'design id')
                    (self.root / '.locks').mkdir(exist_ok=True)
                    held = open(self.root / '.locks' / f'{did}.lock', 'a')
                    fcntl.flock(held, fcntl.LOCK_EX)
                yield
            finally:
                self._depth[did] = depth
                if held:
                    held.close()                         # releases the file lock

    def _path(self, did):
        check_id(did, 'design id')
        return self.root / f'{did}.json'

    def exists(self, did):
        return self._path(did).exists()

    def list(self):
        out = []
        for p in sorted(self.root.glob('*.json')):
            try:
                d = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            out.append({'id': d['id'], 'name': d.get('name'), 'revision': d.get('revision', 0),
                        'components': len(d.get('components', [])), 'joints': len(d.get('joints', [])),
                        'updated': d.get('updated')})
        return out

    def get(self, did):
        p = self._path(did)
        if not p.exists():
            raise NotFound(did)
        raw = json.loads(p.read_text())
        return with_owner(normalize_design(raw), raw.get('owner'))

    def _write(self, design):
        p = self._path(design['id'])
        tmp = p.with_suffix(f'.{os.getpid()}.{threading.get_ident()}.tmp')
        tmp.write_text(json.dumps(design, indent=1))
        os.replace(tmp, p)

    def _snapshot(self, design):
        """Keep a full copy of every revision so an earlier design can be restored."""
        d = self.root / 'versions' / design['id']
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{design['revision']}.json").write_text(json.dumps(design))
        for old in sorted(d.glob('*.json'), key=lambda p: int(p.stem))[:-KEEP_VERSIONS]:
            old.unlink()

    def versions(self, did):
        d = self.root / 'versions' / check_id(did, 'design id')
        return sorted(int(p.stem) for p in d.glob('*.json')) if d.exists() else []

    def get_version(self, did, revision):
        p = self.root / 'versions' / check_id(did, 'design id') / f'{int(revision)}.json'
        if not p.exists():
            raise NotFound(f'{did}@{revision}')
        raw = json.loads(p.read_text())
        return with_owner(normalize_design(raw), raw.get('owner'))

    def _audit(self, did, entry):
        with open(self.root / f'{did}.history.jsonl', 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def create(self, design, actor='system', overwrite=False):
        design = with_owner(normalize_design(design), design.get('owner'))
        with self._lock(design['id']):
            if self.exists(design['id']) and not overwrite:
                raise Conflict(f"design '{design['id']}' already exists")
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            design['revision'] = 1
            design['created'] = design.get('created') or now
            design['updated'] = now
            self._write(design)
            self._snapshot(design)
            self._audit(design['id'], {'at': now, 'actor': actor, 'op': 'create', 'revision': 1})
        return design

    def delete(self, did, actor='system'):
        with self._lock(did):
            p = self._path(did)
            if not p.exists():
                raise NotFound(did)
            p.unlink()
            shutil.rmtree(self.root / 'versions' / did, ignore_errors=True)
            self._audit(did, {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'actor': actor,
                              'op': 'delete'})

    def mutate(self, did, fn, op, actor='system', expected_revision=None, detail=None):
        """fn(design_copy) -> (new_design | None, result). None means 'do not save'."""
        with self._lock(did):
            current = self.get(did)
            if expected_revision is not None and int(expected_revision) != current['revision']:
                raise Conflict(f"design '{did}' is at revision {current['revision']}, "
                               f"not {expected_revision}; re-read and retry")
            new, result = fn(copy.deepcopy(current))
            if new is None:
                return current, result, False
            new = with_owner(normalize_design(new), current.get('owner'))     # a change never changes the owner
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            new['revision'] = current['revision'] + 1
            new['created'] = current.get('created')
            new['updated'] = now
            self._write(new)
            self._snapshot(new)
            self._audit(did, {'at': now, 'actor': actor, 'op': op, 'revision': new['revision'],
                              'detail': detail})
            return new, result, True

    def history(self, did, limit=200):
        p = self.root / f'{did}.history.jsonl'
        if not p.exists():
            return []
        lines = p.read_text().splitlines()[-limit:]
        return [json.loads(x) for x in lines]
