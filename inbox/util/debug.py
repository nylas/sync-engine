"""Utilities for debugging failures in development/staging."""
from functools import wraps
import collections
import time
import traceback
import gevent.hub
import greenlet
import pdb
from inbox.log import log_uncaught_errors, get_logger
from pyinstrument import Profiler
import signal


MAX_BLOCKING_TIME = 5


def raise_once(exc_class, counter=collections.Counter()):
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


class Tracer(object):
    """Simple tracking of time spent in greenlets. Usage:
    >>> tracer = Tracer()
    >>> tracer.set()  # start tracing
    >>> # do stuff
    >>> tracer.log_stats()

    Parameters
    ----------
    max_blocking_time: int
        Log a warning if a greenlet blocks for more than max_blocking_time
        seconds.
    max_stats: int
    """
    def __init__(self, max_blocking_time=MAX_BLOCKING_TIME):
        self.max_blocking_time = max_blocking_time
        self.time_spent_by_id = collections.defaultdict(float)
        self.time_spent_by_context = collections.defaultdict(float)
        self.total_switches = 0
        self._hub = gevent.hub.get_hub()
        self._last_switch_time = None
        self.log = get_logger()

    def set(self):
        self.start_time = time.time()
        greenlet.settrace(self._trace)

    def log_stats(self, max_stats=60):
        total_time = round(time.time() - self.start_time, 2)
        greenlets_by_cost = sorted(self.time_spent_by_context.items(),
                                   key=lambda (k, v): v, reverse=True)
        formatted_times = {k: round(v, 2) for k, v in
                           greenlets_by_cost[:max_stats]}
        self.log.info('greenlet stats',
                      times=formatted_times,
                      total_switches=self.total_switches,
                      total_time=total_time)

    def _trace(self, event, (origin, target)):
        self.total_switches += 1
        current_time = time.time()
        if self._last_switch_time is not None:
            time_spent = current_time - self._last_switch_time
            self.time_spent_by_id[id(origin)] += time_spent
            if origin is not self._hub:
                context = getattr(origin, 'context', None)
            else:
                context = 'hub'
            self.time_spent_by_context[context] += time_spent
            if origin is not self._hub and time_spent > self.max_blocking_time:
                self.log.warning('greenlet blocked', blocked_time=time_spent,
                                 frame=self._format_frame(origin.gr_frame))
        self._last_switch_time = current_time

    def _format_frame(self, frame):
        name = frame.f_globals.get('__name__')
        while (frame is not None and
               (name is None or name.startswith('gevent'))):
            frame = frame.f_back
            name = frame.f_globals.get('__name__')
        return '\t'.join(traceback.format_stack(frame))


def trace_greenlets():
    t = Tracer()
    t.set()
    while True:
        gevent.sleep(60)
        t.log_stats()


def bind_context(gr, role, account_id, *args):
    """Bind a human-interpretable "context" to the greenlet `gr`, for
    execution-tracing purposes. The context consists of the greenlet's role
    (e.g., "foldersyncengine"), the account_id it's operating on, and possibly
    additional values (e.g., folder id, device id)."""
    gr.context = ':'.join([role, str(account_id)] + [str(arg) for arg in args])
