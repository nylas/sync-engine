import logging
from colorlog import ColoredFormatter

def configure_logging():
    # For now we're using the root logger for everything.
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatter = ColoredFormatter(
            "%(log_color)s[%(levelname)-.1s %(asctime)s %(module)s:%(lineno)s]%(reset)s %(message)s",
            reset=True,
            log_colors={
                    'DEBUG':    'cyan',
                    'INFO':     'green',
                    'WARNING':  'yellow',
                    'ERROR':    'red',
                    'CRITICAL': 'red',
            }
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # XXX TODO add another handler here to output log to a file

    return logger
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
