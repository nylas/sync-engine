import time

import pytest
import _mysql_exceptions

from gevent import GreenletExit
from gevent import socket
from sqlalchemy.exc import StatementError
from inbox.util.concurrency import retry_with_logging


class MockLogger(object):

    def __init__(self):
        self.call_count = 0

    def error(self, *args, **kwargs):
        self.call_count += 1


class FailingFunction(object):
    __name__ = 'FailingFunction'

    def __init__(self, exc_type, max_executions=3, delay=0):
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


@pytest.mark.usefixtures('mock_gevent_sleep')
def test_retry_with_logging():
    logger = MockLogger()
    failing_function = FailingFunction(ValueError)
    retry_with_logging(failing_function, logger=logger, backoff_delay=0)
    assert logger.call_count == failing_function.max_executions - 1
    assert failing_function.call_count == failing_function.max_executions


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
    assert logger.call_count == 0
    assert failing_function.call_count == 1


@pytest.mark.usefixtures('mock_gevent_sleep')
def test_no_logging_until_many_transient_error():
    transient = [
        socket.timeout,
        socket.error,
        _mysql_exceptions.OperationalError(
            "(_mysql_exceptions.OperationalError) (1213, 'Deadlock "
            "found when trying to get lock; try restarting transaction')"),
        _mysql_exceptions.OperationalError(
            "(_mysql_exceptions.OperationalError) Lost connection to MySQL "
            "server during query"),
        _mysql_exceptions.OperationalError(
            "(_mysql_exceptions.OperationalError) MySQL server has gone away."),
        _mysql_exceptions.OperationalError(
            "(_mysql_exceptions.OperationalError) Can't connect to MySQL "
            "server on 127.0.0.1"),
        _mysql_exceptions.OperationalError(
            "(_mysql_exceptions.OperationalError) Max connect timeout reached "
            "while reaching hostgroup 71"),
        StatementError(
            message="?", statement="SELECT *", params={},
            orig=_mysql_exceptions.OperationalError(
                "(_mysql_exceptions.OperationalError) MySQL server has gone away.")),
    ]

    for transient_exc in transient:
        logger = MockLogger()
        failing_function = FailingFunction(transient_exc, max_executions=2)
        retry_with_logging(failing_function, logger=logger)

        assert logger.call_count == 0, '{} should not be logged'.format(transient_exc)
        assert failing_function.call_count == 2

        failing_function = FailingFunction(socket.error, max_executions=21)
        retry_with_logging(failing_function, logger=logger)

        assert logger.call_count == 1
        assert failing_function.call_count == 21

        failing_function = FailingFunction(socket.error, max_executions=2)


@pytest.mark.usefixtures('mock_gevent_sleep')
def test_logging_on_critical_error():
    critical = [
        TypeError("Example TypeError"),
        StatementError(
            message="?", statement="SELECT *", params={}, orig=None),
        StatementError(
            message="?", statement="SELECT *", params={},
            orig=_mysql_exceptions.OperationalError(
                "(_mysql_exceptions.OperationalError) Incorrect string value "
                "'\\xE7\\x(a\\x84\\xE5'")),
        _mysql_exceptions.OperationalError(
            "(_mysql_exceptions.OperationalError) Incorrect string value "
            "'\\xE7\\x(a\\x84\\xE5'"),
        _mysql_exceptions.IntegrityError(
            "(_mysql_exceptions.IntegrityError) Column not found"),
    ]

    for critical_exc in critical:
        logger = MockLogger()
        failing_function = FailingFunction(critical_exc, max_executions=2)
        retry_with_logging(failing_function, logger=logger)

        assert logger.call_count == 1, '{} should be logged'.format(critical_exc)
        assert failing_function.call_count == 2
