from flask import Flask, request, jsonify
from werkzeug.exceptions import default_exceptions, HTTPException

from inbox.api.kellogs import APIEncoder
from inbox.log import get_logger
from inbox.models import Namespace
from inbox.models.session import session_scope

from ns_api import app as ns_api

app = Flask(__name__)
# Handle both /endpoint and /endpoint/ without redirecting.
# Note that we need to set this *before* registering the blueprint.
app.url_map.strict_slashes = False


def default_json_error(ex):
    """ Exception -> flask JSON responder """
    logger = get_logger()
    logger.error('Uncaught error thrown by Flask/Werkzeug', exc_info=ex)
    response = jsonify(message=str(ex), type='api_error')
    response.status_code = (ex.code
                            if isinstance(ex, HTTPException)
                            else 500)
    return response

# Patch all error handlers in werkzeug
for code in default_exceptions.iterkeys():
    app.error_handler_spec[None][code] = default_json_error


@app.before_request
def auth():
    pass  # no auth in dev VM


@app.after_request
def finish(response):
    origin = request.headers.get('origin')
    if origin:  # means it's just a regular request
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Headers'] = 'Authorization'
        response.headers['Access-Control-Allow-Methods'] = \
            'GET,PUT,POST,DELETE,OPTIONS'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


@app.route('/n/')
def ns_all():
    """ Return all namespaces """
    # We do this outside the blueprint to support the case of an empty
    # public_id.  However, this means the before_request isn't run, so we need
    # to make our own session
    with session_scope() as db_session:
        namespaces = db_session.query(Namespace).all()
        encoder = APIEncoder()
        return encoder.jsonify(namespaces)


@app.route('/')
def home():
    return """
<html><body>
    Check out the <strong><pre style="display:inline;">docs</pre></strong>
    folder for how to use this API.
</body></html>
"""

app.register_blueprint(ns_api)  # /n/<namespace_id>/...
