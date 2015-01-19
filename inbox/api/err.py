from flask import jsonify


class InputError(Exception):
    """Raised on invalid user input (missing required parameter, value too
    long, etc.)"""
    status_code = 400

    def __init__(self, message):
        self.message = message


class NotFoundError(Exception):
    """Raised when a requested resource doesn't exist."""
    status_code = 404

    def __init__(self, message):
        self.message = message


def err(http_code, message, code=None, param=None):
    resp = {
        'type': 'api_error',
        'message': message
    }
    if code:
        resp['code'] = code
    if param:
        resp['param'] = param
    return jsonify(resp), http_code
