"""
Cooperative time budget for expensive geometry work.

A request sets a budget with `time_budget(seconds)`; the long loops (collision sampling, joining, nesting, contact
search) call `check()`, which raises TimeBudgetExceeded once the budget is spent. Nothing is written before the
exception, so a timed-out request never leaves a half-finished design behind. Without a budget `check()` is a no-op.
"""
import contextlib
import contextvars
import time

_deadline = contextvars.ContextVar('board_deadline', default=None)


class TimeBudgetExceeded(RuntimeError):
    def __init__(self, seconds):
        super().__init__(f'the geometry checks did not finish within the {seconds:g} s time budget')
        self.seconds = seconds


@contextlib.contextmanager
def time_budget(seconds):
    """Run the block under a budget of `seconds`; None / 0 keeps whatever budget the caller set."""
    if not seconds:
        yield
        return
    token = _deadline.set((time.monotonic() + seconds, seconds))
    try:
        yield
    finally:
        _deadline.reset(token)


def check():
    d = _deadline.get()
    if d is not None and time.monotonic() > d[0]:
        raise TimeBudgetExceeded(d[1])
