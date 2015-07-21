from flask import request, g, Blueprint, make_response
from flask import jsonify
from sqlalchemy.orm.exc import NoResultFound

from inbox.api.err import APIException, NotFoundError, InputError
from inbox.api.validation import valid_public_id
from inbox.log import get_logger
log = get_logger()
from inbox.models.session import InboxSession

from inbox.models.backends.gmail import GmailAccount
from inbox.models import Calendar

from inbox.ignition import main_engine
engine = main_engine()


app = Blueprint(
    'webhooks',
    'webhooks_api',
    url_prefix='/w')

GOOGLE_CHANNEL_ID_STRING = 'X-Goog-Channel-ID'
GOOGLE_RESOURCE_STATE_STRING = 'X-Goog-Resource-State'
GOOGLE_RESOURCE_ID_STRING = 'X-Goog-Resource-ID'


def resp(http_code, message=None, **kwargs):
    resp = kwargs
    if message:
        resp['message'] = message
    return make_response(jsonify(resp), http_code)


@app.before_request
def start():
    g.db_session = InboxSession(engine)
    g.log = get_logger()

    try:
        watch_state = request.headers[GOOGLE_RESOURCE_STATE_STRING]
        g.watch_channel_id = request.headers[GOOGLE_CHANNEL_ID_STRING]
        g.watch_resource_id = request.headers[GOOGLE_RESOURCE_ID_STRING]
    except KeyError:
        raise InputError('Malformed headers')

    if watch_state == 'sync':
        return resp(204)


@app.after_request
def finish(response):
    if response.status_code == 200:
        g.db_session.commit()
    g.db_session.close()
    return response


@app.errorhandler(APIException)
def handle_input_error(error):
    response = jsonify(message=error.message,
                       type='invalid_request_error')
    response.status_code = error.status_code
    return response


@app.route('/calendar_list_update/<public_account_id>', methods=['POST'])
def calendar_update(public_account_id):

    try:
        valid_public_id(public_account_id)
        account = g.db_session.query(GmailAccount) \
                  .filter(GmailAccount.public_id == public_account_id) \
                  .one()
        account.handle_gpush_notification()
        return resp(200)
    except ValueError:
        raise InputError('Invalid public ID')
    except NoResultFound:
        g.log.info('Getting push notifications for non-existing account',
                    account_public_id=public_account_id)
        raise NotFoundError("Couldn't find account `{0}`"
                            .format(public_account_id))


@app.route('/calendar_update/<public_calendar_id>', methods=['POST'])
def event_update(public_calendar_id):
    try:
        valid_public_id(public_calendar_id)
        calendar = g.db_session.query(Calendar) \
                  .filter(Calendar.public_id == public_calendar_id) \
                  .one()
        calendar.handle_gpush_notification()
        return resp(200)
    except ValueError:
        raise InputError('Invalid public ID')
    except NoResultFound:
        g.log.info('Getting push notifications for non-existing calendar',
                    calendar_public_id=public_calendar_id)
        raise NotFoundError("Couldn't find calendar `{0}`"
                            .format(public_calendar_id))
