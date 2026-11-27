"""
Worker processes for the heavy geometry checks of very large designs.

Each worker is a fresh `python -m board_engine.parallel` that imports only the engine. Unlike multiprocessing's
fork / forkserver / spawn it never re-runs the web app's main module (start-up code, seeding) and never forks a
threaded server process. Tasks and results travel as pickles over the worker's stdin / stdout, one task per worker at
a time, so a large task is only ever sent to a worker that is waiting for it.
"""
import importlib
import os
import pickle
import selectors
import struct
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _send(f, obj):
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    f.write(struct.pack('<Q', len(data)))
    f.write(data)
    f.flush()


def _recv(f):
    head = f.read(8)
    if len(head) < 8:
        raise EOFError
    return pickle.loads(f.read(struct.unpack('<Q', head)[0]))


def main():
    """Worker loop: run ("module.function", args) tasks until stdin closes."""
    inp, out = sys.stdin.buffer, sys.stdout.buffer
    sys.stdout = sys.stderr                     # a stray print must never corrupt the result stream
    while True:
        try:
            name, args = _recv(inp)
        except EOFError:
            return
        module, fn = name.rsplit('.', 1)
        try:
            _send(out, (True, getattr(importlib.import_module(module), fn)(*args)))
        except BaseException as e:  # noqa: BLE001 - reported to the parent, which raises it
            _send(out, (False, f'{type(e).__name__}: {e}'))


def run(tasks, workers, check=None, done=None):
    """Run tasks [("module.function", args), ...] in up to `workers` fresh processes -> results in task order.
    `check()` is called while waiting (raise to stop: every worker is killed); `done(index, result)` as each ends."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (_ROOT, os.environ.get('PYTHONPATH')) if p))
    procs, sel, results, todo = [], selectors.DefaultSelector(), [None] * len(tasks), list(range(len(tasks)))[::-1]
    finished = False
    try:
        for _ in range(min(workers, len(tasks))):
            p = subprocess.Popen([sys.executable, '-m', 'board_engine.parallel'], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, env=env, cwd=_ROOT)
            procs.append(p)
            sel.register(p.stdout, selectors.EVENT_READ, p)
        busy = {}

        def give(p):
            if todo:
                i = todo.pop()
                busy[p.pid] = i
                _send(p.stdin, tasks[i])
        for p in procs:
            give(p)
        while busy:
            if check:
                check()
            for key, _ev in sel.select(timeout=0.5):
                p = key.data
                try:
                    ok, value = _recv(p.stdout)
                except EOFError:
                    raise RuntimeError(f'a geometry worker process stopped unexpectedly (exit code {p.poll()})')
                if not ok:
                    raise RuntimeError(f'geometry worker failed: {value}')
                i = busy.pop(p.pid)
                results[i] = value
                if done:
                    done(i, value)
                give(p)
        finished = True
        return results
    finally:
        for p in procs:
            try:
                p.stdin.close()                 # a finished worker exits when its input ends
            except OSError:
                pass
            if not finished:
                p.kill()                        # stopped early (time budget, failure): do not wait for its task
            p.wait()
        sel.close()


if __name__ == '__main__':
    main()
