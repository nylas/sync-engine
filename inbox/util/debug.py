"""Utilities for debugging failures in development/staging."""
from functools import wraps
import collections
import time
import traceback
import gevent.hub
import gevent._threading  # This is a clone of the *real* threading module
import greenlet
import pdb
import sys
from nylas.logging import get_logger
from nylas.logging.sentry import log_uncaught_errors
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


class Tracer(object):
    """Log if a greenlet blocks the event loop for too long, and optionally log
    statistics on time spent in individual greenlets.

    Parameters
    ----------
    gather_stats: bool
        Whether to periodically log statistics about time spent.
    max_blocking_time: float
        Log a warning if a greenlet blocks for more than max_blocking_time
        seconds.
    """
    def __init__(self, gather_stats=False,
                 max_blocking_time=MAX_BLOCKING_TIME):
        self.gather_stats = gather_stats
        self.max_blocking_time = max_blocking_time
        self.time_spent_by_context = collections.defaultdict(float)
        self.total_switches = 0
        self._last_switch_time = None
        self._switch_flag = False
        self._active_greenlet = None
        self._main_thread_id = gevent._threading.get_ident()
        self._hub = gevent.hub.get_hub()
        self.log = get_logger()

    def start(self):
        self.start_time = time.time()
        greenlet.settrace(self._trace)
        # Spawn a separate OS thread to periodically check if the active
        # greenlet on the main thread is blocking.
        gevent._threading.start_new_thread(self._monitoring_thread, ())

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
        if self.gather_stats and self._last_switch_time is not None:
            time_spent = current_time - self._last_switch_time
            if origin is not self._hub:
                context = getattr(origin, 'context', None)
            else:
                context = 'hub'
            self.time_spent_by_context[context] += time_spent
        self._active_greenlet = target
        self._last_switch_time = current_time
        self._switch_flag = True

    def _check_blocking(self):
        if self._switch_flag is False:
            active_greenlet = self._active_greenlet
            if active_greenlet is not None and active_greenlet != self._hub:
                # greenlet.gr_frame doesn't work on another thread -- we have
                # to get the main thread's frame.
                frame = sys._current_frames()[self._main_thread_id]
                formatted_frame = '\t'.join(traceback.format_stack(frame))
                self.log.warning(
                    'greenlet blocking', frame=formatted_frame,
                    context=getattr(active_greenlet, 'context', None),
                    blocking_greenlet_id=id(active_greenlet))
        self._switch_flag = False

    def _monitoring_thread(self):
        last_logged_stats = time.time()
        try:
            while True:
                self._check_blocking()
                if self.gather_stats and time.time() - last_logged_stats > 60:
                    self.log_stats()
                    last_logged_stats = time.time()
                gevent.sleep(self.max_blocking_time)
        # Swallow exceptions raised during interpreter shutdown.
        except Exception:
            if sys is not None:
                raise


def bind_context(gr, role, account_id, *args):
    """Bind a human-interpretable "context" to the greenlet `gr`, for
    execution-tracing purposes. The context consists of the greenlet's role
    (e.g., "foldersyncengine"), the account_id it's operating on, and possibly
    additional values (e.g., folder id, device id)."""
    gr.context = ':'.join([role, str(account_id)] + [str(arg) for arg in args])
