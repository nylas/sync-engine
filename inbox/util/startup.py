# XXX(dlitz): Most of this is deployment-related stuff that belongs outside the
# main Python invocation.
import os
import sys
import json
import time

from inbox.config import config

from nylas.logging import get_logger
log = get_logger()


def _absolute_path(relative_path):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        relative_path)


def check_sudo():
    if os.getuid() == 0:
        raise Exception("Don't run Inbox as root!")


_TZ_ERROR_TEXT = """
WARNING!

System time is not set to UTC! This is a problem because
imapclient will normalize INTERNALDATE responses to the 'local'
timezone. \n\nYou can fix this by running

$ echo 'UTC' | sudo tee /etc/timezone

and then checking that it worked with

$ sudo dpkg-reconfigure --frontend noninteractive tzdata

"""


def check_tz():
    if time.tzname[time.daylight] != 'UTC':
        sys.exit(_TZ_ERROR_TEXT)


def load_overrides(file_path):
    """
    Convenience function for overriding default configuration.

    file_path : <string> the full path to a file containing valid
                JSON for configuration overrides
    """
    with open(file_path) as data_file:
        try:
            overrides = json.load(data_file)
        except ValueError:
            sys.exit('Failed parsing configuration file at {}'
                     .format(file_path))
        if not overrides:
            log.debug('No config overrides found.')
            return
        assert isinstance(overrides, dict), \
            'overrides must be dictionary'
        config.update(overrides)
        log.debug('Imported config overrides {}'.format(
            overrides.keys()))


def preflight():
    check_sudo()
    check_tz()

    # Print a traceback when the process receives signal SIGSEGV, SIGFPE,
    # SIGABRT, SIGBUS or SIGILL
    import faulthandler
    faulthandler.enable()
