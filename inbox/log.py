"""
Logging configuration.

We configure separate loggers for general server logging and per-user loggers
for mail sync and contact sync.

"""
import os
import sys
import socket
import logging
import traceback

import requests
from colorlog import ColoredFormatter
from gevent import GreenletExit

from inbox.util.file import mkdirp


file_formatter = logging.Formatter(
    "[%(levelname)-.1s %(asctime)s %(module)-8.8s:%(lineno)-4s] %(message)s")


def get_tty_handler():
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
    return tty_handler


def get_logger(account_id=None, purpose=None):
    """ Helper for abstracting away our logger names. """
    if account_id is None:
        return logging.getLogger('inbox.general')
    else:
        if purpose is None:
            purpose = 'mailsync'
        return logging.getLogger('inbox.{1}.{0}'.format(
            account_id, purpose))


def configure_general_logging():
    """ Configure the general server logger to output to screen if a TTY is
        attached, and server.log always.

        Logs are output to a directory configurable via LOGDIR.
    """
    # import here to avoid import loop from config.py
    from .config import config
    assert 'LOGDIR' in config, "LOGDIR not specified in config file"
    assert 'LOGLEVEL' in config, "LOGLEVEL not specified in config file"
    mkdirp(config['LOGDIR'])

    # configure properties that should cascade
    inbox_root_logger = logging.getLogger('inbox')
    inbox_root_logger.setLevel(int(config['LOGLEVEL']))
    # don't pass messages up to the root root logger
    inbox_root_logger.propagate = False

    # log everything to screen
    if sys.stdout.isatty():
        inbox_root_logger.addHandler(get_tty_handler())

    logger = get_logger()

    for handler in logger.handlers:
        logger.removeHandler(handler)

    logfile = os.path.join(config['LOGDIR'], 'server.log')
    file_handler = logging.FileHandler(logfile, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


def configure_logging(account_id, purpose):
    # avoid import loop from config.py
    from .config import config
    logger = get_logger(account_id, purpose)
    logger.propagate = True

    logdir = os.path.join(config['LOGDIR'], str(account_id))
    mkdirp(logdir)
    logfile = os.path.join(logdir, '{0}.log'.format(purpose))
    handler = logging.FileHandler(logfile, encoding='utf-8')
    handler.setFormatter(file_formatter)
    logger.addHandler(handler)

    return logger


def configure_mailsync_logging(account_id):
    """ We log output for each mail sync instance to a different file than the
        main server log, for ease of debugging. Sync logs still go to screen
        too, for now.
    """
    return configure_logging(account_id, "mailsync")


def configure_contacts_logging(account_id):
    """ We log output for each contacts sync instance to a different file than
        the main server log, for ease of debugging. Contacts sync logs still go
        to screen too, for now.
    """
    return configure_logging(account_id, "contacts")


def email_exception(logger, etype, evalue, tb):
    """ Send stringified exception to configured email address. """
    from inbox.config import config

    exc_email_addr = config.get('EXCEPTION_EMAIL_ADDRESS')
    if exc_email_addr is None:
        logger.error("No EXCEPTION_EMAIL_ADDRESS configured!")
    mailgun_api_endpoint = config.get('MAILGUN_API_ENDPOINT')
    if mailgun_api_endpoint is None:
        logger.error("No MAILGUN_API_ENDPOINT configured!")
    mailgun_api_key = config.get('MAILGUN_API_KEY')
    if mailgun_api_key is None:
        logger.error("No MAILGUN_API_KEY configured!")

    r = requests.post(
        mailgun_api_endpoint,
        auth=("api", mailgun_api_key),
        data={"from": "Inbox App Server <{}>".format(exc_email_addr),
              "to": [exc_email_addr],
              "subject": "Uncaught error! {} {}".format(etype, evalue),
              "text": u"""
    Something went wrong on {}. Please investigate. :)

    {}

    """.format(socket.getfqdn(),
               '\t'.join(traceback.format_exception(etype, evalue, tb)))})
    if r.status_code != requests.codes.ok:
        logger.error("Couldn't send exception email: {}".format(r.json()))


class log_uncaught_errors(object):
    """ Helper to log uncaught exceptions raised within the wrapped function.

        Modeled after gevent.util.wrap_errors.

        Parameters
        ----------
        func: function
            The function to wrap.

        logger: logging.Logger, optional
            The logging object to write to.
    """

    def __init__(self, func, logger=None):
        self.func = func
        self.logger = logger or get_logger()

    def _log_failsafe(self, *args, **kwargs):
        # We wrap the logging call in a try/except block so that if it fails
        # for any reason, the *original* error still gets propagated.
        try:
            self.logger.exception(*args, **kwargs)
        except:
            pass

    def __call__(self, *args, **kwargs):
        from inbox.config import config
        func = self.func
        try:
            return func(*args, **kwargs)
        except Exception, e:
            if not isinstance(e, GreenletExit):
                self._log_failsafe("Uncaught error!")
                exc_type, exc_value, exc_tb = sys.exc_info()
                if config.get('EMAIL_EXCEPTIONS'):
                    email_exception(self.logger, exc_type, exc_value, exc_tb)
            raise

    def __str__(self):
        return str(self.func)

    def __repr__(self):
        return repr(self.func)

    def __getattr__(self, item):
        return getattr(self.func, item)
