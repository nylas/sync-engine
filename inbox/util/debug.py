"""Utilities for debugging failures in development/staging."""
import pdb
from inbox.log import log_uncaught_errors


def pause_on_exception(exception_type):
    """Decorator that catches exceptions of type exception_type, logs them, and
    drops into pdb. Useful for debugging occasional failures.

    Example
    -------
    >>> @pause_on_exception(ValueError)
    ... def bad_function():
    ...     # Do stuff
    ...     raise ValueError
    """
    def wrapper(func):
        def wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_type:
                log_uncaught_errors()
                pdb.post_mortem()
        return wrapped
    return wrapper
