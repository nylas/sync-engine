from flask import jsonify


def err(http_code, message, code=None, param=None):
    resp = dict(
        type='invalid_request_error',
        message=message,
        )
    if code:
        resp['code'] = code
    if param:
        resp['param'] = param
    return jsonify(resp), http_code
