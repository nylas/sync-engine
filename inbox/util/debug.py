"""Utilities for debugging failures in development/staging."""
from functools import wraps
from pyinstrument import Profiler
import signal


def profile(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler = Profiler()
        profiler.start()
        r = func(*args, **kwargs)
        profiler.stop()
        print profiler.output_text(color=True)
        return r
    return wrapper


def attach_pyinstrument_profiler():
    """Run the pyinstrument profiler in the background and dump its output to
    stdout when the process receives SIGTRAP. In general, you probably want to
    use the facilities in inbox.util.profiling instead."""
    profiler = Profiler()
    profiler.start()

    def handle_signal(signum, frame):
        print profiler.output_text(color=True)
        # Work around an arguable bug in pyinstrument in which output gets
        # frozen after the first call to profiler.output_text()
        delattr(profiler, '_root_frame')

    signal.signal(signal.SIGTRAP, handle_signal)


def bind_context(gr, role, account_id, *args):
    """Bind a human-interpretable "context" to the greenlet `gr`, for
    execution-tracing purposes. The context consists of the greenlet's role
    (e.g., "foldersyncengine"), the account_id it's operating on, and possibly
    additional values (e.g., folder id, device id).

    TODO(emfree): this should move to inbox/instrumentation.
    """
    gr.context = ':'.join([role, str(account_id)] + [str(arg) for arg in args])
