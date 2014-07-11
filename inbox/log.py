"""
Logging configuration.

Mostly based off http://www.structlog.org/en/0.4.1/standard-library.html.

"""
import sys
import socket
import traceback

import requests
import colorlog
import structlog
from structlog._frames import _find_first_app_frame_and_name
from inbox.config import config
import logging
import logging.handlers


def configure_logging(is_prod):
    tty_handler = logging.StreamHandler()
    if not is_prod:
        # Use a more human-friendly format.
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s[%(levelname)s]%(reset)s %(message)s',
            reset=True, log_colors={'DEBUG': 'cyan', 'INFO': 'green',
                                    'WARNING': 'yellow', 'ERROR': 'red',
                                    'CRITICAL': 'red'})
    else:
        formatter = logging.Formatter('%(message)s')
    tty_handler.setFormatter(formatter)
    # Configure the root logger
    logging.getLogger().addHandler(tty_handler)


def _record_level(logger, name, event_dict):
    """Record the log level ('info', 'warning', etc.) in the structlog event
    dictionary."""
    event_dict['level'] = name
    return event_dict


def _record_module(logger, name, event_dict):
    """Record the module and line where the logging call was invoked."""
    f, name = _find_first_app_frame_and_name(additional_ignores=['inbox.log'])
    event_dict['module'] = '{}:{}'.format(name, f.f_lineno)
    return event_dict


structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt='iso', utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _record_module,
        _record_level,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
get_logger = structlog.get_logger


def email_exception(logger, etype, evalue, tb):
    """ Send stringified exception to configured email address. """
    exc_email_addr = config.get('EXCEPTION_EMAIL_ADDRESS')
    if exc_email_addr is None:
        logger.error('No EXCEPTION_EMAIL_ADDRESS configured!')
    mailgun_api_endpoint = config.get('MAILGUN_API_ENDPOINT')
    if mailgun_api_endpoint is None:
        logger.error('No MAILGUN_API_ENDPOINT configured!')
    mailgun_api_key = config.get('MAILGUN_API_KEY')
    if mailgun_api_key is None:
        logger.error('No MAILGUN_API_KEY configured!')

    r = requests.post(
        mailgun_api_endpoint,
        auth=('api', mailgun_api_key),
        data={'from': "Inbox App Server <{}>".format(exc_email_addr),
              'to': [exc_email_addr],
              'subject': "Uncaught error! {} {}".format(etype, evalue),
              'text': u"""
    Something went wrong on {}. Please investigate. :)

    {}

    """.format(socket.getfqdn(),
               '\t'.join(traceback.format_exception(etype, evalue, tb)))})
    if r.status_code != requests.codes.ok:
        logger.error("Couldn't send exception email: {}".format(r.json()))


def log_uncaught_errors(logger=None):
    """
    Helper to log uncaught exceptions.

    Parameters
    ----------
    logger: structlog.BoundLogger, optional
        The logging object to write to.
    """
    logger = logger or get_logger()
    logger.error('Uncaught error', exc_info=True)
    if config.get('EMAIL_EXCEPTIONS'):
        email_exception(logger, *sys.exc_info())
