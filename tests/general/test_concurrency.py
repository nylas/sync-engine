import time

import pytest
from gevent import GreenletExit

from inbox.util.concurrency import retry_wrapper, resettable_counter


class MockLogger(object):
    def __init__(self):
        self.call_count = 0

    def exception(self, *args, **kwargs):
        self.call_count += 1


class FailingFunction(object):
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


def test_retry_wrapper():
    logger = MockLogger()
    failing_function = FailingFunction(ValueError)
    with pytest.raises(ValueError):
        retry_wrapper(failing_function, logger=logger)
    assert logger.call_count == 3
    assert failing_function.call_count == 3


def test_no_logging_on_greenlet_exit():
    logger = MockLogger()
    failing_function = FailingFunction(GreenletExit)
    retry_wrapper(failing_function, logger=logger)
    assert logger.call_count == 0
    assert failing_function.call_count == 1


def test_retry_count_resets():
    logger = MockLogger()
    counter = resettable_counter(reset_interval=0)

    failing_function = FailingFunction(ValueError, max_executions=6,
                                       delay=.1)

    retry_wrapper(failing_function, logger=logger, failure_counter=counter)

    assert logger.call_count == 5
    assert failing_function.call_count == 6
