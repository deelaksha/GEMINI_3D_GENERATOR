"""
Compile progress reporting.

A caller that wants live progress (the streaming compile endpoint) installs a reporter with `reporting(fn)`; the
compiler calls `report(stage, done, total)` at real stage boundaries and inside its long loops. Without a reporter
`report()` is a no-op, so every other caller behaves exactly as before. A reporter may raise CompileCancelled to stop
the work; it derives from BaseException so the compiler's `except Exception` safety nets never swallow it.
"""
import contextlib
import contextvars

_reporter = contextvars.ContextVar('board_progress', default=None)


class CompileCancelled(BaseException):
    """The client went away; stop compiling. Nothing is written before it is raised."""


@contextlib.contextmanager
def reporting(fn):
    token = _reporter.set(fn)
    try:
        yield
    finally:
        _reporter.reset(token)


def report(stage, done=None, total=None):
    fn = _reporter.get()
    if fn is not None:
        fn(stage, done, total)
