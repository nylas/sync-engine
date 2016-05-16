from flask import jsonify, make_response
from nylas.logging import get_logger
log = get_logger()


class APIException(Exception):
    pass


class InputError(APIException):
    """Raised on invalid user input (missing required parameter, value too
    long, etc.)"""
    status_code = 400

    def __init__(self, message):
        self.message = message
        super(InputError, self).__init__(message)


class NotFoundError(APIException):
    """Raised when a requested resource doesn't exist."""
    status_code = 404

    def __init__(self, message):
        self.message = message
        super(NotFoundError, self).__init__(message)


class ConflictError(APIException):
    status_code = 409

    def __init__(self, message):
        self.message = message
        super(ConflictError, self).__init__(message)


class AccountInvalidError(APIException):
    """ Raised when an account's credentials are not valid. """
    status_code = 403
    message = "This action can't be performed because the account's " \
              "credentials are out of date. Please reauthenticate and try " \
              "again."


class AccountStoppedError(APIException):
    """ Raised when an account has been stopped. """
    status_code = 403
    message = "This action can't be performed because the account's sync " \
              "has been stopped. Please contact support@nylas.com to resume " \
              "sync."


class AccountDoesNotExistError(APIException):
    """ Raised when an account does not exist (for example, if it was deleted). """
    status_code = 404
    message = "The account does not exist."


def err(http_code, message, **kwargs):
    log.info('Returning API error to client',
             http_code=http_code, message=message, kwargs=kwargs)
    resp = {
        'type': 'api_error',
        'message': message
    }
    resp.update(kwargs)
    return make_response(jsonify(resp), http_code)
