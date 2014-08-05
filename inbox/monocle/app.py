#!/usr/bin/python
import json
import datetime

from flask import Flask, g, request

from sqlalchemy.orm.exc import NoResultFound

from inbox.ignition import main_engine
from inbox.models.session import InboxSession
from inbox.models import Account
from inbox.api.err import err

engine = main_engine(pool_size=5)

app = Flask(__name__, static_url_path='')
app.debug = False


@app.before_request
def start():
    g.db_session = InboxSession(engine)


@app.after_request
def finish(response):
    g.db_session.close()
    return response


@app.route('/')
def root():
        return app.send_static_file('index.html')


@app.route('/accounts', methods=['GET'])
def accounts():
    accounts = g.db_session.query(Account).all()
    accounts_info = [acct.calculate_sync_status(g.db_session) for acct in
                     accounts]

    return json.dumps(accounts_info, cls=DateTimeJSONEncoder)


@app.route('/account/<account_id>', methods=['GET'])
def account(account_id):
    try:
        account = g.db_session.query(Account).get(account_id)
    except NoResultFound:
        return err(404, 'No account with id `{0}`'.format(account_id))

    if 'action' in request.args:
        action = request.args.get('action', None)
        if action == 'stop':
            if account.sync_enabled:
                account.stop_sync()
                g.db_session.add(account)
                g.db_session.commit()
        elif action == 'start':
            account.start_sync()
            g.db_session.add(account)
            g.db_session.commit()

    if account:
        folders_info = [foldersyncstatus.metrics for foldersyncstatus in
                        account.foldersyncstatuses]
        sync_status = account.sync_status
    else:
        folders_info = []
        sync_status = {}

    return json.dumps({"account": sync_status,
                       "folders": folders_info}, cls=DateTimeJSONEncoder)


class DateTimeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return str(obj)
        else:
            return super(DateTimeJSONEncoder, self).default(obj)


if __name__ == '__main__':
    from setproctitle import setproctitle
    import os
    setproctitle('monocle')
    os.environ['DEBUG'] = 'true' if app.debug else 'false'
    app.run(host='127.0.0.1')
