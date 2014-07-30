#!/usr/bin/python
from subprocess import call
import json
import datetime

from flask import Flask, g, render_template, request

from sqlalchemy.orm.exc import NoResultFound

from inbox.ignition import main_engine
from inbox.models.session import InboxSession
from inbox.models import Account
from inbox.api.err import err

engine = main_engine(pool_size=5)

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


def _render_account(account):
    acct_info = account.sync_status

    template = 'account.html' if account.provider != 'eas' else \
        'eas_account.html'

    return render_template(template, account=acct_info)


@app.route('/account/<account_id>', methods=['GET'])
def account(account_id):
    try:
        account = g.db_session.query(Account).get(account_id)
    except NoResultFound:
        return err(404, 'No account with id `{0}`'.format(account_id))

    if 'action' in request.args:
        root_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 '..', '..')
        bin_path = os.path.abspath(os.path.join(root_path, 'bin'))
        inbox_sync = os.path.join(bin_path, 'inbox-sync')

        action = request.args.get('action', None)
        if action == 'stop':
            print "stopping: ", account_id
            call([inbox_sync, "stop", account.email_address])
            account = g.db_session.query(Account).get(account_id)
        elif action == 'start':
            print "starting: ", account_id
            call([inbox_sync, "start", account.email_address])
            account = g.db_session.query(Account).get(account_id)

    return _render_account(account)


@app.route('/_accounts/<account_id>', methods=['GET'])
def _account(account_id):
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
    import os
    os.environ['DEBUG'] = 'true' if app.debug else 'false'
    app.run(host='0.0.0.0')
