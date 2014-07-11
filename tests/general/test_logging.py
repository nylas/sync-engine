import json
import sys
import traceback

from inbox.log import log_uncaught_errors, get_logger


def test_root_filelogger(config, log):
    logger = get_logger()
    logger.info('INFO')
    logger.warning('WARNING')
    logger.error('ERROR')
    # NOTE: This slurps the whole logfile. Hope it's not big.
    log_contents = open(config.get_required('TEST_LOGFILE'), 'r').read()

    assert all(phrase in log_contents
               for phrase in ('INFO', 'WARNING', 'ERROR'))


# Helper functions for test_log_uncaught_errors


def error_throwing_function():
    raise ValueError


def test_log_uncaught_errors(config, log):
    try:
        error_throwing_function()
    except:
        log_uncaught_errors()

    with open(config.get_required('TEST_LOGFILE'), 'r') as f:
        last_log_entry = json.loads(f.readlines()[-1])

    assert 'exception' in last_log_entry
    exc_info = last_log_entry['exception']

    assert 'ValueError' in exc_info
    assert 'GreenletExit' not in exc_info
    # Check that the traceback is logged. The traceback stored in
    # sys.exc_info() contains an extra entry for the test_log_uncaught_errors
    # frame, so just look for the rest of the traceback.
    tb = sys.exc_info()[2]
    for call in traceback.format_tb(tb)[1:]:
        assert call in exc_info
