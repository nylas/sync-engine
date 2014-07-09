import sys
import time
import functools

import gevent
import zerorpc

from inbox.log import get_logger, log_uncaught_errors
from inbox.mailsync.reporting import report_killed
log = get_logger()


def resettable_counter(max_count=3, reset_interval=300):
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
          exc_callback=None, fail_callback=None):
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
        for _ in resettable_counter():
            try:
                return func(*args, **kwargs)
            except gevent.GreenletExit, e:
                # GreenletExit isn't actually a subclass of Exception.
                # This is also considered to be a successful execution
                # (somebody intentionally killed the greenlet).
                raise
            except Exception, e:
                if exc_callback is not None:
                    exc_callback()
                if not should_retry_on(e):
                    break
        if fail_callback is not None:
            fail_callback()
        raise

    return wrapped


def retry_with_logging(func, logger=None, retry_classes=None,
                       fail_classes=None):
    callback = lambda: log_uncaught_errors(logger)
    return retry(func, exc_callback=callback, retry_classes=retry_classes,
                 fail_classes=fail_classes)()


def retry_and_report_killed(func, account_id, folder_name=None, logger=None,
                            retry_classes=None, fail_classes=None):
    exc_callback = lambda: log_uncaught_errors(logger)
    fail_callback = lambda: report_killed(account_id, folder_name)
    return retry(func, exc_callback=exc_callback,
                 fail_callback=fail_callback, retry_classes=retry_classes,
                 fail_classes=fail_classes)()


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
    return gevent.Greenlet.spawn(retry_with_logging, m)


def print_dots():
    """This Greenlet prints dots to the console which is useful for making
    sure that other greenlets are properly not blocking."""
    def m():
        while True:
            sys.stdout.write("."),
            sys.stdout.flush()
            time.sleep(.02)
    gevent.Greenlet.spawn(m)
