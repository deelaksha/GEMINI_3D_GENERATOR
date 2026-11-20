"""
File-backed design store: one JSON document per design + an append-only history log.

Every mutation goes through DesignStore.mutate(), which:
  * loads the latest revision under a per-design lock,
  * rejects stale writes when the caller supplies expected_revision,
  * runs the mutation on a deep copy (callers validate inside it),
  * bumps the revision, writes atomically and records an audit entry.
"""
import copy
import json
import os
import threading
import time
from pathlib import Path

from .model import check_id, normalize_design


class NotFound(KeyError):
    pass


class Conflict(RuntimeError):
    pass


class DesignStore:
    backend = 'file'
    persistent = True      # False when the server had to fall back to a temp directory
    config_error = None

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks = {}
        self._guard = threading.Lock()

    def _lock(self, did):
        with self._guard:
            return self._locks.setdefault(did, threading.RLock())

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
        return normalize_design(json.loads(p.read_text()))

    def _write(self, design):
        p = self._path(design['id'])
        tmp = p.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(design, indent=1))
        os.replace(tmp, p)

    def _audit(self, did, entry):
        with open(self.root / f'{did}.history.jsonl', 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def create(self, design, actor='system', overwrite=False):
        design = normalize_design(design)
        with self._lock(design['id']):
            if self.exists(design['id']) and not overwrite:
                raise Conflict(f"design '{design['id']}' already exists")
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            design['revision'] = 1
            design['created'] = design.get('created') or now
            design['updated'] = now
            self._write(design)
            self._audit(design['id'], {'at': now, 'actor': actor, 'op': 'create', 'revision': 1})
        return design

    def delete(self, did, actor='system'):
        with self._lock(did):
            p = self._path(did)
            if not p.exists():
                raise NotFound(did)
            p.unlink()
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
            new = normalize_design(new)
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            new['revision'] = current['revision'] + 1
            new['created'] = current.get('created')
            new['updated'] = now
            self._write(new)
            self._audit(did, {'at': now, 'actor': actor, 'op': op, 'revision': new['revision'],
                              'detail': detail})
            return new, result, True

    def history(self, did, limit=200):
        p = self.root / f'{did}.history.jsonl'
        if not p.exists():
            return []
        lines = p.read_text().splitlines()[-limit:]
        return [json.loads(x) for x in lines]
