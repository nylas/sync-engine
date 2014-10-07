import sys
import time
import functools
import random

import gevent

from inbox.log import get_logger, log_uncaught_errors
from inbox.mailsync.reporting import report_killed
log = get_logger()
BACKOFF_DELAY = 30  # seconds to wait before retrying after a failure
MAX_COUNT = 100  # maximum number of tries before plain giving up
RESET_INTERVAL = 300  # amount of time to pass before resetting the counter


def _resettable_counter(max_count, reset_interval):
    """
    Iterator which yields max_count times before returning, but resets if
    not called for reset_interval seconds.

    """
    count = 0
    last_increment_at = time.time()
    while count < max_count:
        yield
        if time.time() - last_increment_at > reset_interval:
            count = 1
        else:
            count += 1
        last_increment_at = time.time()


def retry(func, retry_classes=None, fail_classes=None,
          exc_callback=None, fail_callback=None, **reset_params):
    """
    Executes the callable func, retrying on uncaught exceptions.

    Arguments
    ---------
    func : function
    exc_callback : function, optional
    Function to execute if an exception is raised within func (e.g., log
    something)
    fail_callback: function, optional
        Function to execute if we exit without func ever returning successfully
        (e.g., log something more severe)
    retry_classes: list of Exception subclasses, optional
        Configures what to retry on. If specified, func is retried only if one
        of these exceptions is raised. Default is to retry on all exceptions.
    fail_classes: list of Exception subclasses, optional
        Configures what not to retry on. If specified, func is /not/ retried if
        one of these exceptions is raised.
    """
    if (fail_classes and retry_classes and
            set(fail_classes).intersection(retry_classes)):
        raise ValueError("Can't include exception classes in both fail_on and "
                         "retry_on")

    def should_retry_on(exc):
        if fail_classes and any(isinstance(exc, exc_type) for exc_type in
                                fail_classes):
            return False
        if retry_classes and not any(isinstance(exc, exc_type) for exc_type in
                                     retry_classes):
            return False
        return True

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        for _ in _resettable_counter(reset_params.get('max_count', MAX_COUNT),
                                     reset_params.get('reset_interval',
                                                      RESET_INTERVAL)):
            try:
                return func(*args, **kwargs)
            except gevent.GreenletExit, e:
                # GreenletExit isn't actually a subclass of Exception.
                # This is also considered to be a successful execution
                # (somebody intentionally killed the greenlet).
                raise
            except Exception, e:
                if not should_retry_on(e):
                    break
                if exc_callback is not None:
                    exc_callback()

            # Sleep a bit so that we don't poll too quickly and re-encounter
            # the error. Also add a random delay to prevent herding effects.
            initial_sleep = reset_params.get('backoff_delay',
                                             BACKOFF_DELAY)
            if initial_sleep:
                additional_sleep = int(random.uniform(1, 10))
                gevent.sleep(initial_sleep + additional_sleep)

        if fail_callback is not None:
            fail_callback()
        raise

    return wrapped


def retry_with_logging(func, logger=None, retry_classes=None,
                       fail_classes=None, account_id=None, **reset_params):
    callback = lambda: log_uncaught_errors(logger, account_id)
    return retry(func, exc_callback=callback, retry_classes=retry_classes,
                 fail_classes=fail_classes, **reset_params)()


def retry_and_report_killed(func, account_id, folder_name=None, logger=None,
                            retry_classes=None, fail_classes=None,
                            **reset_params):
    exc_callback = lambda: log_uncaught_errors(logger=logger,
                                               account_id=account_id)
    fail_callback = lambda: report_killed(account_id, folder_name)
    return retry(func, exc_callback=exc_callback,
                 fail_callback=fail_callback, retry_classes=retry_classes,
                 fail_classes=fail_classes, **reset_params)()


def print_dots():
    """This Greenlet prints dots to the console which is useful for making
    sure that other greenlets are properly not blocking."""
    def m():
        while True:
            sys.stdout.write("."),
            sys.stdout.flush()
            time.sleep(.02)
    gevent.Greenlet.spawn(m)
