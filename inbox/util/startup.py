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
        raise Exception("Don't run the Nylas Sync Engine as root!")


# TODO(menno) - It's good to have all servers use UTC for general
# sanity, but the IMAPClient concern mentioned in the warning text
# below can be avoided. When an IMAPClient instance's
# `normalise_times` attribute is set to False IMAPClient will return
# unnormalised, timezone-aware timestamps. Changing this is probably
# non-trival because timezone and non-timezone-aware timestamps don't
# mix. Some care will be required to ensure that only timezone-aware
# timestamps are used where they might mix with timestamps originating
# from IMAPClient.

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


def load_overrides(file_path, loaded_config=config):
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
        loaded_config.update(overrides)
        log.debug('Imported config overrides {}'.format(
            overrides.keys()))


def preflight():
    check_sudo()
    check_tz()

    # Print a traceback when the process receives signal SIGSEGV, SIGFPE,
    # SIGABRT, SIGBUS or SIGILL
    import faulthandler
    faulthandler.enable()
