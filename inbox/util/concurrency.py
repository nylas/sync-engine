import functools
import random

import gevent

from nylas.logging import get_logger
from nylas.logging.sentry import log_uncaught_errors
log = get_logger()
BACKOFF_DELAY = 30  # seconds to wait before retrying after a failure


def retry(func, retry_classes=None, fail_classes=None, exc_callback=None,
          backoff_delay=BACKOFF_DELAY):
    """
    Executes the callable func, retrying on uncaught exceptions.

    Arguments
    ---------
    func : function
    exc_callback : function, optional
        Function to execute if an exception is raised within func
        (e.g., log something)
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
        if fail_classes and isinstance(exc, tuple(fail_classes)):
            return False
        if retry_classes and not isinstance(exc, tuple(retry_classes)):
            return False
        return True

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        while True:
            try:
                return func(*args, **kwargs)
            except gevent.GreenletExit, e:
                # GreenletExit isn't actually a subclass of Exception.
                # This is also considered to be a successful execution
                # (somebody intentionally killed the greenlet).
                raise
            except Exception, e:
                if not should_retry_on(e):
                    raise
                if exc_callback is not None:
                    exc_callback()

            # Sleep a bit so that we don't poll too quickly and re-encounter
            # the error. Also add a random delay to prevent herding effects.
            gevent.sleep(backoff_delay + int(random.uniform(1, 10)))

    return wrapped


def retry_with_logging(func, logger=None, retry_classes=None,
                       fail_classes=None, account_id=None,
                       backoff_delay=BACKOFF_DELAY):
    callback = lambda: log_uncaught_errors(logger, account_id=account_id)
    return retry(func, exc_callback=callback, retry_classes=retry_classes,
                 fail_classes=fail_classes, backoff_delay=backoff_delay)()
