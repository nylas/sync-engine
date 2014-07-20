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


MAX_EXCEPTION_LENGTH = 10000


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
    # Configure the root logger.
    root_logger = logging.getLogger()
    root_logger.addHandler(tty_handler)
    # Set loglevel DEBUG if config value is missing.
    root_logger.setLevel(config.get('LOGLEVEL', 10))


def safe_format_exception(etype, value, tb, limit=None):
    """Similar to structlog._format_exception, but truncate the exception part.
    This is because SQLAlchemy exceptions can sometimes have ludicrously large
    exception strings."""
    if tb:
        list = ['Traceback (most recent call last):\n']
        list = list + traceback.format_tb(tb, limit)
    else:
        list = []
    exc_only = traceback.format_exception_only(etype, value)
    # Normally exc_only is a list containing a single string.  For syntax
    # errors it may contain multiple elements, but we don't really need to
    # worry about that here.
    exc_only[0] = exc_only[0][:MAX_EXCEPTION_LENGTH]
    list = list + exc_only
    return '\t'.join(list)


def _record_level(logger, name, event_dict):
    """Processor that records the log level ('info', 'warning', etc.) in the
    structlog event dictionary."""
    event_dict['level'] = name
    return event_dict


def _record_module(logger, name, event_dict):
    """Processor that records the module and line where the logging call was
    invoked."""
    f, name = _find_first_app_frame_and_name(additional_ignores=['inbox.log'])
    event_dict['module'] = '{}:{}'.format(name, f.f_lineno)
    return event_dict


def _format_string_renderer(_, __, event_dict):
    """Processor to be used with the BoundLogger class below to properly handle
    messages of the form
    `log.info('some message to format %s', some_value')`."""
    positional_args = event_dict.get('_positional_args')
    if positional_args:
        event_dict['event'] = event_dict['event'] % positional_args
        del event_dict['_positional_args']
    return event_dict


def _safe_exc_info_renderer(_, __, event_dict):
    """Processor that formats exception info safely."""
    exc_info = event_dict.pop('exc_info', None)
    if exc_info:
        if not isinstance(exc_info, tuple):
            exc_info = sys.exc_info()
        event_dict['exception'] = safe_format_exception(*exc_info)
    return event_dict


class BoundLogger(structlog._base.BoundLoggerBase):
    """Adaptation of structlog.stdlib.BoundLogger to accept positional
    arguments. See https://github.com/hynek/structlog/pull/23/
    (we can remove this if that ever gets merged)."""
    def debug(self, event=None, *args, **kw):
        return self._proxy_to_logger('debug', event, *args, **kw)

    def info(self, event=None, *args, **kw):
        return self._proxy_to_logger('info', event, *args, **kw)

    def warning(self, event=None, *args, **kw):
        return self._proxy_to_logger('warning', event, *args, **kw)

    warn = warning

    def error(self, event=None, *args, **kw):
        return self._proxy_to_logger('error', event, *args, **kw)

    def critical(self, event=None, *args, **kw):
        return self._proxy_to_logger('critical', event, *args, **kw)

    def exception(self, event=None, *args, **kw):
        kw['exc_info'] = True
        return self._proxy_to_logger('error', event, *args, **kw)

    def _proxy_to_logger(self, method_name, event=None, *event_args,
                         **event_kw):
        if event_args:
            event_kw['_positional_args'] = event_args
        return super(BoundLogger, self)._proxy_to_logger(method_name, event,
                                                         **event_kw)


structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt='iso', utc=True),
        structlog.processors.StackInfoRenderer(),
        _safe_exc_info_renderer,
        _record_module,
        _record_level,
        _format_string_renderer,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=BoundLogger,
    cache_logger_on_first_use=True,
)
get_logger = structlog.get_logger


def email_exception(logger, account_id, etype, evalue, tb):
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

    account_str = 'account_id {}: '.format(account_id) if account_id else ''
    r = requests.post(
        mailgun_api_endpoint,
        auth=('api', mailgun_api_key),
        data={'from': "Inbox App Server <{}>".format(exc_email_addr),
              'to': [exc_email_addr],
              'subject': "Uncaught error! {}{} {}".format(account_str, etype,
                                                          evalue),
              'text': u"""
    Something went wrong on {}. Please investigate. :)

    {}

    """.format(socket.getfqdn(),
               safe_format_exception(etype, evalue, tb))})
    if r.status_code != requests.codes.ok:
        logger.error("Couldn't send exception email: {}".format(r.text))


def log_uncaught_errors(logger=None, account_id=None):
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
        email_exception(logger, account_id, *sys.exc_info())
