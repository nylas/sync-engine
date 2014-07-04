import json
import datetime

from flask import Flask, g, render_template

from sqlalchemy.orm.exc import NoResultFound

from inbox.ignition import engine
from inbox.models.session import InboxSession
from inbox.models import register_backends, Account
register_backends()
from inbox.api.err import err

app = Flask(__name__)


@app.before_request
def start():
    g.db_session = InboxSession(engine)


@app.after_request
def finish(response):
    return response


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/accounts', methods=['GET'])
def all_accounts():
    return render_template('accounts.html')


@app.route('/_accounts', methods=['GET'])
def _all_accounts():
    accounts = g.db_session.query(Account).all()
    accounts_info = [acct.sync_status for acct in accounts]

    return json.dumps(accounts_info, cls=DateTimeJSONEncoder)


@app.route('/accounts/<account_id>', methods=['GET'])
def for_account(account_id):
    try:
        account = g.db_session.query(Account).get(account_id)
    except NoResultFound:
        return err(404, 'No account with id `{0}`'.format(account_id))

    acct_info = account.sync_status

    template = 'for_account.html' if account.provider != 'eas' else \
        'for_eas_account.html'

    return render_template(template, account=acct_info)


@app.route('/_accounts/<account_id>', methods=['GET'])
def _for_account(account_id):
    try:
        account = g.db_session.query(Account).get(account_id)
    except NoResultFound:
        return err(404, 'No account with id `{0}`'.format(account_id))

    folders_info = [foldersyncstatus.metrics for foldersyncstatus in
                    account.foldersyncstatuses]

    return json.dumps(folders_info, cls=DateTimeJSONEncoder)


class DateTimeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return str(obj)
        else:
            return super(DateTimeJSONEncoder, self).default(obj)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
