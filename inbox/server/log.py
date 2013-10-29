import logging
from colorlog import ColoredFormatter

from ..util.file import mkdirp, safe_filename

import sys, os

tty_formatter = ColoredFormatter(
        # wish we could left-truncate name!
        "%(name)-20.20s %(log_color)s[%(levelname)-.1s %(asctime)s %(module)-8.8s:%(lineno)-4s]%(reset)s %(message)s",
        reset=True,
        log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red',
        })

tty_handler = logging.StreamHandler()
tty_handler.setFormatter(tty_formatter)

file_formatter = logging.Formatter( "[%(levelname)-.1s %(asctime)s %(module)-8.8s:%(lineno)-4s] %(message)s")

def get_logger(account=None):
    """ Helper for abstracting away our logger names. """
    if account is None:
        return logging.getLogger('inbox.server.general')
    else:
        return logging.getLogger('inbox.server.sync.{0}'.format(account.id))

def configure_logging():
    """ Configure the general server logger to output to screen if a TTY is
        attached, and server.log always.

        Logs are output to a directory configurable via LOGDIR.
    """
    # import here to avoid import loop from config.py
    from .config import config
    mkdirp(config['LOGDIR'])

    # configure properties that should cascade
    inbox_root_logger = logging.getLogger('inbox.server')
    inbox_root_logger.setLevel(logging.INFO)
    # don't pass messages up to the root root logger
    inbox_root_logger.propagate = False

    # log everything to screen
    if sys.stdout.isatty():
        inbox_root_logger.addHandler(tty_handler)

    logger = get_logger()

    for handler in logger.handlers:
        logger.removeHandler(handler)

    logfile = os.path.join(config['LOGDIR'], 'server.log')
    file_handler = logging.FileHandler(logfile)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger

def configure_sync_logging(account):
    """ We log output for each sync instance to a different file than the
        main server log, for ease of debugging. Sync logs still go to screen
        too, for now.
    """
    # import here to avoid import loop from config.py
    from .config import config
    logger = get_logger(account)
    logger.propagate = True

    logdir = os.path.join(
            config['LOGDIR'], safe_filename(account.email_address))
    mkdirp(logdir)
    # XXX we may want to rotate the log file eventually
    logfile = os.path.join(logdir, 'sync.log')
    handler = logging.FileHandler(logfile)
    handler.setFormatter(file_formatter)
    logger.addHandler(handler)

    return logger
