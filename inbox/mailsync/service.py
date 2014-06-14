""" ZeroRPC interface to syncing. """
import socket

from collections import defaultdict

from inbox.contacts.remote_sync import ContactSync
from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models import Account
from inbox.mailsync.backends.base import register_backends


def notify(account_id, mtype, message):
    """ Pass a message on to the notification dispatcher which deals with
        pubsub stuff for connected clients.
    """
    pass
    # self.log.info("message from {0}: [{1}] {2}".format(
    # account_id, mtype, message))


class SyncService(object):
    def __init__(self):
        self.monitor_cls_for = register_backends()

        self.log = get_logger()
        # { account_id: MailSyncMonitor() }
        self.monitors = dict()
        # READ ONLY from API calls, writes happen from callbacks from monitor
        # greenlets.
        # { 'account_id': { 'state': 'initial sync', 'status': '0'} }
        # 'state' can be ['initial sync', 'poll']
        # 'status' is the percent-done for initial sync, polling start time
        # otherwise
        # all data in here ought to be msgpack-serializable!
        self.statuses = defaultdict(dict)

        self.contact_sync_monitors = dict()

        # Restart existing active syncs.
        # (Later we will want to partition these across different machines!)
        with session_scope() as db_session:
            # XXX: I think we can do some sqlalchemy magic to make it so we
            # can query on the attribute sync_active.
            for account_id, in db_session.query(Account.id)\
                    .filter(~Account.sync_host.is_(None)):
                self.start_sync(account_id)

    def start_sync(self, account_id=None):
        """ Starts all syncs if account_id not specified.
            If account_id doesn't exist, does nothing.
        """
        results = {}
        if account_id:
            account_id = int(account_id)
        with session_scope() as db_session:
            query = db_session.query(Account)
            if account_id is not None:
                query = query.filter_by(id=account_id)
            fqdn = socket.getfqdn()
            for acc in query:
                if acc.provider not in self.monitor_cls_for:
                    self.log.info('Inbox does not currently support {0}\
                        '.format(acc.provider))
                    continue
                self.log.info('Starting sync for account {0}'
                              .format(acc.email_address))
                if acc.sync_host is not None and acc.sync_host != fqdn:
                    results[acc.id] = \
                        'acc {0} is syncing on host {1}'.format(
                            acc.email_address, acc.sync_host)
                elif acc.id not in self.monitors:
                    try:
                        acc.sync_lock()

                        def update_status(account_id, state, status):
                            """ I really really wish I were a lambda """
                            folder, progress = status
                            self.statuses[account_id][folder] \
                                = (state, progress)
                            notify(account_id, state, status)

                        monitor = self.monitor_cls_for[acc.provider](
                            acc.id, acc.namespace.id, acc.email_address,
                            acc.provider, update_status)
                        self.monitors[acc.id] = monitor
                        monitor.start()
                        # For Gmail accounts, also start contacts sync
                        if acc.provider == 'Gmail':
                            contact_sync = ContactSync(acc.id)
                            self.contact_sync_monitors[acc.id] = contact_sync
                            contact_sync.start()
                        acc.sync_host = fqdn
                        db_session.add(acc)
                        db_session.commit()
                        results[acc.id] = 'OK sync started'
                    except Exception as e:
                        self.log.error(e.message)
                        results[acc.id] = 'ERROR error encountered: {0}'.format(e)
                else:
                    results[acc.id] = 'OK sync already started'
        if account_id:
            if account_id in results:
                return results[account_id]
            else:
                return "OK no such user"
        return results

    def stop_sync(self, account_id=None):
        """ Stops all syncs if account_id not specified.
            If account_id doesn't exist, does nothing.
        """
        results = {}
        if account_id:
            account_id = int(account_id)
        with session_scope() as db_session:
            query = db_session.query(Account)
            if account_id is not None:
                query = query.filter_by(id=account_id)
            fqdn = socket.getfqdn()
            for acc in query:
                if (not acc.id in self.monitors) or \
                        (not acc.sync_active):
                    results[acc.id] = "OK sync stopped already"
                try:
                    if acc.sync_host is None:
                        results[acc.id] = 'Sync not running'
                        continue
                    assert acc.sync_host == fqdn, \
                        "sync host FQDN doesn't match: {0} <--> {1}" \
                        .format(acc.sync_host, fqdn)
                    # XXX Can processing this command fail in some way?
                    self.monitors[acc.id].inbox.put_nowait("shutdown")
                    acc.sync_host = None
                    db_session.add(acc)
                    db_session.commit()
                    acc.sync_unlock()
                    del self.monitors[acc.id]
                    # Also stop contacts sync (only relevant for Gmail
                    # accounts)
                    if acc.id in self.contact_sync_monitors:
                        del self.contact_sync_monitors[acc.id]
                    results[acc.id] = "OK sync stopped"
                except Exception as e:
                    results[acc.id] = 'ERROR error encountered: {0}'.format(e)
        if account_id:
            if account_id in results:
                return results[account_id]
            else:
                return "OK no such user"
        return results

    def sync_status(self, account_id):
        return self.statuses.get(account_id)

    # XXX this should require some sort of auth or something, used from the
    # admin panel
    def status(self):
        return self.statuses
