import logging

from inbox.server.log import get_logger
inbox_logger = get_logger(purpose='api')

# Override default werkzeug before it starts up
werkzeug_log = logging.getLogger('werkzeug')
for handler in werkzeug_log.handlers:
    werkzeug_log.removeHandler(handler)
werkzeug_log.addHandler(inbox_logger)

from flask import Flask, request, Response, g, make_response
from flask import jsonify as flask_jsonify

from werkzeug.exceptions import default_exceptions
from werkzeug.exceptions import HTTPException

from inbox.server.models.tables.base import register_backends
table_mod_for = register_backends()
from inbox.server.models import new_db_session

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


def default_json_error(ex):
    """ Exception -> flask JSON responder """
    app.logger.error("Uncaught error thrown by Flask/Werkzeug: {0}"
                     .format(ex))
    response = flask_jsonify(message=str(ex), type='api_error')
    response.status_code = (ex.code
                            if isinstance(ex, HTTPException)
                            else 500)
    return response

# Patch all error handlers in werkzeug
for code in default_exceptions.iterkeys():
    app.error_handler_spec[None][code] = default_json_error


@app.errorhandler(NotImplementedError)
def handle_not_implemented_error(error):
    response = flask_jsonify(message="API endpoint not yet implemented.",
                             type='api_error')
    response.status_code = 501
    return response


@app.before_request
def auth():
    """
    checks the developer's API token
    """
    auth = request.authorization

    # Prompt for auth
    if not auth or not auth['username']:
        return Response(
            'The Inbox API requires a valid user token.\n'
            'See <a href="https://www.inboxapp.com/docs">'
            'https://www.inboxapp.com/docs</a> for more info.', 401,
            {'WWW-Authenticate':
             'Basic realm="Please enter your access_token as the '
             'username and leave the password field blank."'})

    # if request.method == 'OPTIONS':
    #     # Validate that this URL is a registered app origin
    #     r = make_response('', 200)
    #     origin = request.headers.get('origin')
    #     if not origin:
    #         raise  # TODO


    g.db_session = new_db_session()

    # user_sk = auth['username']
    # TODO make sure user_sk is known
    # if it fails:
    #     return err(401, "Invalid API secret key")

    # add the developer's info to request context
    g.dev_id = '2947687to2yuighsdfasfasdf'

    # TOFIX
    app.logger.warning("Auth for developer_id {0}".format(g.dev_id))

    # TODO check the key here against developer DB
    g.user_id = 1

    # user = db_session.query(User).join(Account)\
    #     .filter_by(id=user_id).one()


@app.after_request
def finish(response):
    session = g.get('db_session')
    if session:
        session.commit()
        session.close()

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
    return "Maybe you're looking for the <a href='docs'>Docs</a>&hellip;"
