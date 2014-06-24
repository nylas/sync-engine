import sys
import signal
import time

import gevent
import zerorpc

from rq import Worker, Queue
from rq.worker import StopRequested, DequeueTimeout

from inbox.log import get_logger, log_uncaught_errors
log = get_logger()


def resettable_counter(max_count=3, reset_interval=300):
    """Iterator which yields max_count times before returning, but resets if
    not called for reset_interval seconds."""
    count = 0
    last_increment_at = time.time()
    while count < max_count:
        yield
        if time.time() - last_increment_at > reset_interval:
            count = 1
        else:
            count += 1
        last_increment_at = time.time()


def retry_wrapper(func, logger=None, failure_counter=None, *args, **kwargs):
    """Executes the callable func, logging and retrying on uncaught exceptions.

    Arguments
    ---------
    func: function
    logger: Logger instance, optional
    failure_counter: iterator, optional
        Can be used to configure retry behavior. falure_counter.next() is
        invoked on each failure; the call to func will be retried until
        StopIteration is raised from failure_counter. Defaults to an instance
        of resettable_counter.
    """
    logger = logger or get_logger()
    failure_counter = failure_counter or resettable_counter()

    for _ in failure_counter:
        try:
            return func(*args, **kwargs)
        except gevent.GreenletExit, e:
            return e
        except Exception, e:
            log_uncaught_errors(logger)
    raise


def make_zerorpc(cls, location):
    assert location, "Location to bind for %s cannot be none!" % cls

    def m():
        """ Exposes `cls` as a ZeroRPC server on the given address+port. """
        s = zerorpc.Server(cls())
        s.bind(location)
        log.info("ZeroRPC: Starting %s at %s" % (cls.__name__, location))
        s.run()
    # By default, when an uncaught error is thrown inside a greenlet, gevent
    # will print the stacktrace to stderr and kill the greenlet. Here we're
    # wrapping m in order to also log uncaught errors to disk.
    return gevent.Greenlet.spawn(retry_wrapper, m)


def print_dots():
    """This Greenlet prints dots to the console which is useful for making
    sure that other greenlets are properly not blocking."""
    def m():
        while True:
            sys.stdout.write("."),
            sys.stdout.flush()
            time.sleep(.02)
    gevent.Greenlet.spawn(m)


# Derived from https://github.com/nvie/rq/issues/303
class GeventWorker(Worker):

    def get_ident(self):
        return id(gevent.getcurrent())

    def __init__(self, *nargs, **kwargs):

        processes = kwargs['processes'] if 'processes' in kwargs else 5

        self.gevent_pool = gevent.pool.Pool(int(processes))

        Worker.__init__(self, *nargs, **kwargs)

    def _install_signal_handlers(self):
        """Installs signal handlers for handling SIGINT and SIGTERM
        gracefully.
        """

        def request_force_stop():
            """Terminates the application (cold shutdown).
            """
            self.log.warning('Cold shut down.')

            self.gevent_pool.kill()

            raise SystemExit()

        def request_stop():
            """Stops the current worker loop but waits for child processes to
            end gracefully (warm shutdown).
            """
            gevent.signal(signal.SIGINT, request_force_stop)
            gevent.signal(signal.SIGTERM, request_force_stop)

            msg = 'Warm shut down requested.'
            self.log.warning(msg)

            # If shutdown is requested in the middle of a job, wait until
            # finish before shutting down
            self.log.debug('Stopping after all greenlets are finished. '
                           'Press Ctrl+C again for a cold shutdown.')
            self._stopped = True
            self.gevent_pool.join()

            raise StopRequested()

        gevent.signal(signal.SIGINT, request_stop)
        gevent.signal(signal.SIGTERM, request_stop)

    def fork_and_perform_job(self, job):
        """Spawns a gevent greenlet to perform the actual work.
        """
        self.gevent_pool.spawn(retry_wrapper, lambda: self.perform_job(job),
                               self.log)

    def dequeue_job_and_maintain_ttl(self, timeout):
        while True:

            while not self.gevent_pool.free_count() > 0:
                gevent.sleep(0.1)

            try:
                job = Queue.dequeue_any(self.queues, timeout,
                                        connection=self.connection)
                # make sure all child jobs finish if queue is empty in burst
                # mode
                if job is None and timeout is None:
                    self.gevent_pool.join()
                return job
            except DequeueTimeout:
                pass

            self.log.debug('Sending heartbeat to prevent worker timeout.')
            self.connection.expire(self.key, self.default_worker_ttl)
