"""Utilities for debugging failures in development/staging."""
from functools import wraps
from collections import Counter
import pdb
from inbox.log import log_uncaught_errors
from pyinstrument import Profiler
import signal


def raise_once(exc_class, counter=Counter()):
    """Add raise_once(exc_class) in your code to raise an instance of exc_class
    at that location, but only once for the program execution time. This is for
    debugging retry logic, etc."""
    if not counter['failures']:
        counter['failures'] += 1
        raise exc_class()


def pause_on_exception(exception_type):
    """Decorator that catches exceptions of type exception_type, logs them, and
    drops into pdb. Useful for debugging occasional failures.

    Example
    -------
    >>> @pause_on_exception(ValueError)
    ... def bad_function():
    ...     # Do stuff
    ...     raise ValueError
    """
    def wrapper(func):
        def wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_type:
                log_uncaught_errors()
                pdb.post_mortem()
        return wrapped
    return wrapper


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


def attach_profiler():
    profiler = Profiler()
    profiler.start()

    def handle_signal(signum, frame):
        print profiler.output_text(color=True)
        # Work around an arguable bug in pyinstrument in which output gets
        # frozen after the first call to profiler.output_text()
        delattr(profiler, '_root_frame')

    signal.signal(signal.SIGTRAP, handle_signal)
