import os
import sys
import traceback
from logging import getLogger

import pytest
from gevent import GreenletExit

from inbox.log import log_uncaught_errors


def test_root_filelogger(config, log):
    log.warning('TEST LOG STATEMENT')
    root_logger = getLogger()
    root_logger.warning('ROOT LOG STATEMENT')
    # NOTE: This slurps the whole logfile. Hope it's not big.
    log_contents = open(os.path.join(config['LOGDIR'], 'server.log'),
                        'r').read()

    assert 'TEST LOG STATEMENT' in log_contents
    assert 'ROOT LOG STATEMENT' not in log_contents


def test_sync_filelogger(config, log):
    pass

# Helper functions for test_log_uncaught_errors


def error_throwing_function():
    raise ValueError


def simulate_greenlet_exit():
    raise GreenletExit


def test_log_uncaught_errors(config, log):
    with pytest.raises(ValueError):
        log_uncaught_errors(error_throwing_function)()
    log_uncaught_errors(simulate_greenlet_exit)
    log_contents = open(os.path.join(config['LOGDIR'], 'server.log'),
                        'r').read()

    assert 'ValueError' in log_contents
    assert 'GreenletExit' not in log_contents
    # Check that the traceback is logged. The traceback stored in
    # sys.exc_info() contains an extra entry for the test_log_uncaught_errors
    # frame, so just look for the rest of the traceback.
    tb = sys.exc_info()[2]
    for call in traceback.format_tb(tb)[1:]:
        assert call in log_contents
