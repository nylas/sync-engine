#!/usr/bin/python
import platform
from subprocess import call
import json
import datetime
from collections import defaultdict
import logging
from logging import FileHandler

from flask import Flask, g, request

from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

from inbox.ignition import main_engine
from inbox.models.session import InboxSession
from inbox.models import Account, backend_module_registry
from inbox.api.err import err
from inbox.util.itert import partition

engine = main_engine(pool_size=5)

app = Flask(__name__, static_url_path='')
app.debug = False

ACCOUNTS_INFO = []
last_calc_at = None
recalc_after = 120


@app.before_request
def start():
    g.db_session = InboxSession(engine, ignore_soft_deletes=False)


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

    app.logger.error('In accounts, last_calc_at, delta: {0}, {1}'.format(
        str(last_calc_at), str(delta)))

    if not last_calc_at or delta >= recalc_after:
        app.logger.error('Recalc')

        ACCOUNTS_INFO = []
        accounts = g.db_session.query(Account).all()
        imap, eas = partition(lambda a: a.provider == 'eas', accounts)

        if imap:
            ACCOUNTS_INFO.extend(calculate_imap_status(g.db_session, imap))

        if eas and 'eas' in backend_module_registry:
            ACCOUNTS_INFO.extend(calculate_eas_status(g.db_session, eas))

        last_calc_at = datetime.datetime.utcnow()

    return json.dumps(ACCOUNTS_INFO, cls=DateTimeJSONEncoder)


def calculate_imap_status(db_session, accts):
        from inbox.models.backends.imap import ImapFolderSyncStatus, ImapUid

        ids = [a.id for a in accts]

        metrics = db_session.query(
            ImapFolderSyncStatus.account_id,
            ImapFolderSyncStatus._metrics).filter(
            ImapFolderSyncStatus.account_id.in_(ids)).all()

        numuids = db_session.query(
            ImapUid.account_id, func.count(ImapUid.id)).group_by(
            ImapUid.account_id).all()

        remote = defaultdict(int)
        for m in metrics:
            remote[m[0]] += m[1].get('remote_uid_count', 0)

        local = defaultdict(int)
        for m in numuids:
            local[m[0]] = m[1]

        accounts_info = []
        for a in accts:
            status = a.sync_status
            status.update(remote_count=remote[a.id], local_count=local[a.id])

            accounts_info.append(status)

        return accounts_info


def calculate_eas_status(db_session, accts):
        from inbox.models.backends.eas import EASFolderSyncStatus, EASUid

        ids = [a.id for a in accts]

        metrics = db_session.query(
            EASFolderSyncStatus.account_id,
            EASFolderSyncStatus._metrics).filter(
            EASFolderSyncStatus.account_id.in_(ids)).all()

        numuids = db_session.query(
            EASUid.easaccount_id, func.count(EASUid.id)).group_by(
            EASUid.easaccount_id).all()

        remote = defaultdict(int)
        for m in metrics:
            remote[m[0]] += m[1].get('total_remote_count', 0)

        local = defaultdict(int)
        for m in numuids:
            local[m[0]] = m[1]

        accounts_info = []
        for a in accts:
            status = a.sync_status
            status.update(remote_count=remote[a.id], local_count=local[a.id])

            accounts_info.append(status)

        return accounts_info


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

    if app.debug:
        handler = FileHandler('monocle_debug.log')
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)

    app.run(host='127.0.0.1')
