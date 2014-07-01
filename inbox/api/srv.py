import logging

from gevent.pywsgi import WSGIHandler

from inbox.log import get_logger
inbox_logger = get_logger(purpose='api')

# Override default werkzeug before it starts up
werkzeug_log = logging.getLogger('werkzeug')
for handler in werkzeug_log.handlers:
    werkzeug_log.removeHandler(handler)
werkzeug_log.addHandler(inbox_logger)

from flask import Flask, request
from flask import logging as flask_logging

def mock_create_logger(app):
    return inbox_logger
flask_logging.create_logger = mock_create_logger

from inbox.api.kellogs import jsonify, cereal
from inbox.models import register_backends, Namespace
from inbox.models.session import session_scope
table_mod_for = register_backends()

from ns_api import app as ns_api

app = Flask(__name__)
# Handle both /endpoint and /endpoint/ without redirecting.
# Note that we need to set this *before* registering the blueprint.


# gevent.pywsgi bullshit. see
# http://stackoverflow.com/questions/9444405/gunicorn-and-websockets
def log_request(self, *args):
    log = self.server.log
    if log:
        if hasattr(log, "info"):
            log.info(self.format_request(*args))
        elif hasattr(log, "debug"):
            log.debug(self.format_request(*args))
        elif hasattr(log, "warning"):
            log.warning(self.format_request(*args))
        elif hasattr(log, "error"):
            log.error(self.format_request(*args))
        else:
            log.write(self.format_request(*args))
WSGIHandler.log_request = log_request


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

@app.route('/n/')
def ns_all():
    """ Return all namespaces """
    # We do this outside the blueprint to support the case of an empty public_id.
    # However, this means the before_request isn't run, so we need to make our own session
    with session_scope() as db_session:
        namespaces = db_session.query(Namespace).all()
        return jsonify(namespaces)

@app.route('/')
def home():
    return """
<html><body>
    Check out the <strong><pre style="display:inline">docs</pre></strong> folder
    for how to use this API.
</body></html>
"""

app.url_map.strict_slashes = False
app.register_blueprint(ns_api)  # /n/<namespace_id>/...
