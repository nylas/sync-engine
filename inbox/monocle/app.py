#!/usr/bin/python
import platform
from subprocess import call
import json
import datetime
import logging
from logging import FileHandler

from flask import Flask, g, request

from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

from inbox.ignition import main_engine
from inbox.models.session import InboxSession
from inbox.models import Account, backend_module_registry
from inbox.api.err import err

engine = main_engine(pool_size=5)

app = Flask(__name__, static_url_path='')
app.debug = True

ACCOUNTS_INFO = []
last_calc_at = None
recalc_after = 120


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
    global last_calc_at, ACCOUNTS_INFO

    delta = (datetime.datetime.utcnow() - last_calc_at).seconds if \
        last_calc_at else None

    app.logger.info('last_calc_at, delta: {0}, {1}'.format(
        str(last_calc_at), str(delta)))

    if not last_calc_at or delta >= recalc_after:
        app.logger.info('Recalculating')

        ACCOUNTS_INFO = {}
        eas = []
        imap = []

        accounts = g.db_session.query(Account.id, Account.discriminator,
                                      Account._sync_status).all()

        for a in accounts:
            ACCOUNTS_INFO[a[0]] = a[2]

            if a[1] == 'easaccount':
                eas.append(a[0])
            else:
                imap.append(a[0])

        if imap:
            calculate_imap_status(g.db_session, imap, ACCOUNTS_INFO)

        if eas and 'eas' in backend_module_registry:
            calculate_eas_status(g.db_session, eas, ACCOUNTS_INFO)

        last_calc_at = datetime.datetime.utcnow()

    return json.dumps(ACCOUNTS_INFO.values(), cls=DateTimeJSONEncoder)


def calculate_imap_status(db_session, accts, accounts_info):
        from inbox.models.backends.imap import ImapFolderSyncStatus, ImapUid

        metrics = db_session.query(
            ImapFolderSyncStatus.account_id,
            ImapFolderSyncStatus._metrics).filter(
            ImapFolderSyncStatus.account_id.in_(accounts_info.keys())).all()

        numuids = db_session.query(
            ImapUid.account_id, func.count(ImapUid.id)).group_by(
            ImapUid.account_id).all()

        for m in metrics:
            remote_count = accounts_info[m[0]].get('remote_count', 0)
            remote_count += m[1].get('remote_uid_count', 0)

            accounts_info[m[0]]['remote_count'] = remote_count

        for m in numuids:
            accounts_info[m[0]]['local_count'] = m[1]

        return accounts_info


def calculate_eas_status(db_session, accts, accounts_info):
        from inbox.models.backends.eas import EASFolderSyncStatus, EASUid

        metrics = db_session.query(
            EASFolderSyncStatus.account_id,
            EASFolderSyncStatus._metrics).filter(
            EASFolderSyncStatus.account_id.in_(accounts_info.keys())).all()

        numuids = db_session.query(
            EASUid.easaccount_id, func.count(EASUid.id)).group_by(
            EASUid.easaccount_id).all()

        for m in metrics:
            remote_count = accounts_info[m[0]].get('remote_count', 0)
            remote_count += m[1].get('total_remote_count', 0)

            accounts_info[m[0]]['remote_count'] = remote_count

        for m in numuids:
            accounts_info[m[0]]['local_count'] = m[1]

        return accounts_info


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
            if account.sync_enabled:
                print "stopping: ", account_id
                account.stop_sync()
        elif action == 'start':
            print "starting: ", account_id
            account.start_sync(platform.node())

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
    import os
    os.environ['DEBUG'] = 'true' if app.debug else 'false'

    if app.debug:
        handler = FileHandler('debug.log')
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)

    app.run(host='127.0.0.1')
