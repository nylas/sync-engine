import collections
import math
import signal
import socket
import sys
import time
import traceback
import gevent.hub
import gevent._threading  # This is a clone of the *real* threading module
import greenlet
import psutil
from inbox.config import config
from inbox.util.stats import get_statsd_client
from nylas.logging import get_logger


MAX_BLOCKING_TIME = 5
GREENLET_SAMPLING_INTERVAL = 1
LOGGING_INTERVAL = 60


class ProfileCollector(object):
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
    max_blocking_time: float
        Log a warning if a greenlet blocks for more than max_blocking_time
        seconds.
    """

    def __init__(self,
                 max_blocking_time=MAX_BLOCKING_TIME,
                 sampling_interval=GREENLET_SAMPLING_INTERVAL,
                 logging_interval=LOGGING_INTERVAL):
        self.max_blocking_time = max_blocking_time
        self.sampling_interval = sampling_interval
        self.logging_interval = logging_interval

        self.time_spent_by_context = collections.defaultdict(float)
        self.total_switches = 0
        self._last_switch_time = None
        self._switch_flag = False
        self._active_greenlet = None
        self._main_thread_id = gevent._threading.get_ident()
        self._hub = gevent.hub.get_hub()

        self.total_cpu_time = 0
        self.process = psutil.Process()
        self.pending_avgs = {1: 0, 5: 0, 15: 0}
        self.cpu_avgs = {1: 0, 5: 0, 15: 0}
        self.hostname = socket.gethostname().replace(".", "-")
        self.process_name = str(config.get("PROCESS_NAME", "unknown"))
        self.log = get_logger()
        # We need a new client instance here because this runs in its own
        # thread.
        self.statsd_client = get_statsd_client()

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
            'pending_avgs': self.pending_avgs,
            'cpu_avgs': self.cpu_avgs,
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
                      total_time=total_time,
                      pending_avgs=self.pending_avgs)
        self._publish_load_avgs()

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

    def _calculate_pending_avgs(self):
        # Calculate a "load average" for greenlet scheduling in roughly the
        # same way as /proc/loadavg.  I.e., a 1/5/15-minute
        # exponentially-damped moving average of the number of greenlets that
        # are waiting to run.
        pendingcnt = self._hub.loop.pendingcnt
        for k, v in self.pending_avgs.items():
            exp = math.exp(- self.sampling_interval / (60. * k))
            self.pending_avgs[k] = exp * v + (1. - exp) * pendingcnt

    def _calculate_cpu_avgs(self):
        times = self.process.cpu_times()
        new_total_time = times.user + times.system
        delta = new_total_time - self.total_cpu_time
        for k, v in self.cpu_avgs.items():
            exp = math.exp(- self.sampling_interval / (60. * k))
            self.cpu_avgs[k] = exp * v + (1. - exp) * delta
        self.total_cpu_time = new_total_time

    def _publish_load_avgs(self):
        for k, v in self.pending_avgs.items():
            path = 'pending_avg.{}.{}.{:02d}'.format(self.hostname,
                                                     self.process_name, k)
            self.statsd_client.gauge(path, v)
        for k, v in self.cpu_avgs.items():
            path = 'cpu_avg.{}.{}.{:02d}'.format(self.hostname,
                                                 self.process_name, k)
            self.statsd_client.gauge(path, v)

    def _monitoring_thread(self):
        last_logged_stats = time.time()
        last_checked_blocking = time.time()
        try:
            while True:
                self._calculate_pending_avgs()
                self._calculate_cpu_avgs()
                now = time.time()
                if now - last_checked_blocking > self.max_blocking_time:
                    self._check_blocking()
                    last_checked_blocking = now
                if now - last_logged_stats > self.logging_interval:
                    self.log_stats()
                    last_logged_stats = now
                gevent.sleep(self.sampling_interval)
        # Swallow exceptions raised during interpreter shutdown.
        except Exception:
            if sys is not None:
                raise
