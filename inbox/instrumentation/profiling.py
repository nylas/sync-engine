import collections
import signal
import sys
import time
import traceback
import gevent.hub
import gevent._threading  # This is a clone of the *real* threading module
import greenlet
from nylas.logging import get_logger


MAX_BLOCKING_TIME = 5


class CPUSampler(object):
    """A simple stack sampler for low-overhead CPU profiling: samples the call
    stack every `interval` seconds and keeps track of counts by frame. Because
    this uses signals, it only works on the main thread."""

    def __init__(self, interval=0.005):
        self.interval = interval
        self._started = None
        self._stack_counts = collections.defaultdict(int)

    def start(self):
        self._started = time.time()
        try:
            signal.signal(signal.SIGVTALRM, self._sample)
        except ValueError:
            raise ValueError('Can only sample on the main thread')

        signal.setitimer(signal.ITIMER_VIRTUAL, self.interval, 0)

    def _sample(self, signum, frame):
        stack = []
        while frame is not None:
            stack.append(self._format_frame(frame))
            frame = frame.f_back

        stack = ';'.join(reversed(stack))
        self._stack_counts[stack] += 1
        signal.setitimer(signal.ITIMER_VIRTUAL, self.interval, 0)

    def _format_frame(self, frame):
        return '{}({})'.format(frame.f_code.co_name,
                               frame.f_globals.get('__name__'))

    def stats(self):
        if self._started is None:
            return ''
        elapsed = time.time() - self._started
        lines = ['elapsed {}'.format(elapsed),
                 'granularity {}'.format(self.interval)]
        ordered_stacks = sorted(self._stack_counts.items(),
                                key=lambda kv: kv[1], reverse=True)
        lines.extend(['{} {}'.format(frame, count)
                      for frame, count in ordered_stacks])
        return '\n'.join(lines) + '\n'

    def reset(self):
        self._started = time.time()
        self._stack_counts = collections.defaultdict(int)


class GreenletTracer(object):
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

    def __init__(self, max_blocking_time=MAX_BLOCKING_TIME):
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

    def stats(self):
        total_time = time.time() - self.start_time
        idle_fraction = self.time_spent_by_context.get('hub', 0) / total_time
        return {
            'times': self.time_spent_by_context,
            'idle_fraction': idle_fraction,
            'total_time': total_time,
            'total_switches': self.total_switches
        }

    def log_stats(self, max_stats=60):
        total_time = round(time.time() - self.start_time, 2)
        greenlets_by_cost = sorted(self.time_spent_by_context.items(),
                                   key=lambda k_v: k_v[1], reverse=True)
        formatted_times = {k: round(v, 2) for k, v in
                           greenlets_by_cost[:max_stats]}
        self.log.info('greenlet stats',
                      times=formatted_times,
                      total_switches=self.total_switches,
                      total_time=total_time)

    def _trace(self, event, xxx_todo_changeme):
        (origin, target) = xxx_todo_changeme
        self.total_switches += 1
        current_time = time.time()
        if self._last_switch_time is not None:
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
