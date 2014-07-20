import json
import sys
import traceback

from inbox.log import (log_uncaught_errors, get_logger, safe_format_exception,
                       MAX_EXCEPTION_LENGTH)


class ReallyVerboseError(Exception):
    def __str__(self):
        return 10**6 * 'A'


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


def test_safe_format_exception():
    try:
        raise ReallyVerboseError()
    except ReallyVerboseError:
        # Check that the stdlib exception formatting would be large
        assert (len('\t'.join(traceback.format_exception(*sys.exc_info()))) >
                2 * MAX_EXCEPTION_LENGTH)
        exc = safe_format_exception(*sys.exc_info())
        # And check that the resulting string is reasonably-sized.
        assert len(exc) < 2 * MAX_EXCEPTION_LENGTH
