import time

import pytest
from gevent import GreenletExit

from inbox.util.concurrency import (retry, retry_with_logging,
                                    resettable_counter)
from inbox.log import log_uncaught_errors


class MockLogger(object):
    def __init__(self):
        self.call_count = 0

    def exception(self, *args, **kwargs):
        self.call_count += 1


class FailingFunction(object):
    __name__ = 'FailingFunction'

    def __init__(self, exc_type, max_executions=6, delay=0):
        self.exc_type = exc_type
        self.max_executions = max_executions
        self.delay = delay
        self.call_count = 0

    def __call__(self):
        self.call_count += 1
        time.sleep(self.delay)
        if self.call_count < self.max_executions:
            raise self.exc_type
        return


def test_retry_with_logging():
    logger = MockLogger()
    failing_function = FailingFunction(ValueError)
    with pytest.raises(ValueError):
        retry_with_logging(failing_function, logger=logger)
    assert logger.call_count == 3
    assert failing_function.call_count == 3


def test_no_logging_on_greenlet_exit():
    logger = MockLogger()
    failing_function = FailingFunction(GreenletExit)
    with pytest.raises(GreenletExit):
        retry_with_logging(failing_function, logger=logger)
    assert logger.call_count == 0
    assert failing_function.call_count == 1


def test_selective_retry():
    logger = MockLogger()
    failing_function = FailingFunction(ValueError)
    with pytest.raises(ValueError):
        retry_with_logging(failing_function, logger=logger,
                           fail_classes=[ValueError])
    assert logger.call_count == 1
    assert failing_function.call_count == 1


def test_retry_count_resets(monkeypatch):
    monkeypatch.setattr('inbox.util.concurrency.resettable_counter',
                        lambda: resettable_counter(reset_interval=0))
    logger = MockLogger()

    failing_function = FailingFunction(ValueError, max_executions=6,
                                       delay=.1)

    exc_callback = lambda: log_uncaught_errors(logger)

    retry(failing_function, exc_callback=exc_callback)()

    assert logger.call_count == 5
    assert failing_function.call_count == 6
