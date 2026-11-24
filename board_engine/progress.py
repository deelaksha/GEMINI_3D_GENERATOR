"""
Compile progress reporting.

A caller that wants live progress (the streaming compile endpoint) installs a reporter with `reporting(fn)`; the
compiler calls `report(stage, done, total, **info)` at real stage boundaries and inside its long loops (`info` names
the boards being worked on, or carries the one-off geometry preview). Without a reporter `report()` is a no-op and
`active()` is False, so every other caller behaves exactly as before and never builds the extra info. A reporter
may raise CompileCancelled to stop the work; it derives from BaseException so the compiler's `except Exception`
safety nets never swallow it.
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


def active():
    return _reporter.get() is not None


def report(stage, done=None, total=None, **info):
    fn = _reporter.get()
    if fn is not None:
        fn(stage, done, total, info)
