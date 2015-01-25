from flask import jsonify


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


def err(http_code, message, **kwargs):
    resp = {
        'type': 'api_error',
        'message': message
    }
    resp.update(kwargs)
    return jsonify(resp), http_code
