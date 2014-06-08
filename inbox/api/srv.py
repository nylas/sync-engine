import logging

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

from inbox.models.tables.base import register_backends
table_mod_for = register_backends()

from ns_api import app as ns_api


app = Flask(__name__)
app.register_blueprint(ns_api)  # /n/<namespace_id>/...


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
    return """
<html><body>
    Check out the <strong><pre style="display:inline">docs</pre></strong> folder
    for how to use this API.
</body></html>
"""
