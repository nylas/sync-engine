import logging

from inbox.server.log import get_logger
inbox_logger = get_logger(purpose='api')

# Override default werkzeug before it starts up
werkzeug_log = logging.getLogger('werkzeug')
for handler in werkzeug_log.handlers:
    werkzeug_log.removeHandler(handler)
werkzeug_log.addHandler(inbox_logger)

from flask import Flask, request

from inbox.server.models.tables.base import register_backends, Namespace
table_mod_for = register_backends()
from inbox.server.models import session_scope
from inbox.server.models.kellogs import jsonify

from ns_api import app as ns_api
from u_api import app as u_api
from docs import app as docs_blueprint

# Provider name for contacts added via this API
INBOX_PROVIDER_NAME = 'inbox'

app = Flask(__name__)
app.register_blueprint(ns_api)  # /n/<namespace_id>/...
app.register_blueprint(u_api)   # /u/<user_id>/...
app.register_blueprint(docs_blueprint)   # /docs


# Set flask logger as ours
for handler in app.logger.handlers:
    app.logger.removeHandler(handler)
app.logger.addHandler(inbox_logger)



@app.before_request
def auth():
    pass  # no auth in dev VM

@app.after_request
def finish(response):
    origin = request.headers.get('origin')
    if origin:  # means it's just a regular request
        response.headers['Access-Control-Allow-Origin'] = origin  # Just echo origin
        response.headers['Access-Control-Allow-Headers'] = 'Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
        response.headers['Access-Control-Allow-Credentials'] = 'true'

    app.logger.info("Sending response {0}".format(response))
    return response


@app.route('/')
def home():
    return "Maybe you're looking for the <a href='docs'>Docs</a>?"


@app.route('/n/')
def ns_all():
    """
    Display a listing of all namespaces at /n/
    This is done to help with development, along with no authentication.
    """
    with session_scope() as db_session:
        namespaces = db_session.query(Namespace).all()
        return jsonify(namespaces)
