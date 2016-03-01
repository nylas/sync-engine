from flask import jsonify, make_response


class APIException(Exception):
    pass


class InputError(APIException):
    """Raised on invalid user input (missing required parameter, value too
    long, etc.)"""
    status_code = 400

    def __init__(self, message):
        self.message = message


class NotFoundError(APIException):
    """Raised when a requested resource doesn't exist."""
    status_code = 404

    def __init__(self, message):
        self.message = message


class ConflictError(APIException):
    status_code = 409

    def __init__(self, message):
        self.message = message


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


def err(http_code, message, **kwargs):
    resp = {
        'type': 'api_error',
        'message': message
    }
    resp.update(kwargs)
    return make_response(jsonify(resp), http_code)
