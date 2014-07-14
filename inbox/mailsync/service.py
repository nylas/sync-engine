""" ZeroRPC interface to syncing. """
import platform
import gevent

from inbox.contacts.remote_sync import ContactSync
from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models import Account

from inbox.mailsync.backends import module_registry


class SyncService(object):
    def __init__(self, poll_interval=1):
        self.monitor_cls_for = {mod.PROVIDER: getattr(
            mod, mod.SYNC_MONITOR_CLS) for mod in module_registry.values()
            if hasattr(mod, 'SYNC_MONITOR_CLS')}

        self.log = get_logger()
        self.monitors = {}
        self.contact_sync_monitors = {}
        self.poll_interval = poll_interval

        with session_scope() as db_session:
            # Restart existing active syncs.
            # (Later we'll want to partition these across different machines)
            for account_id, in db_session.query(Account.id).filter(
                    ~Account.sync_host.is_(None)):
                self.start_sync(account_id)

        # In a separate greenlet, check for new accounts that are registered.
        gevent.spawn(self._new_account_listener)

    def _new_account_listener(self):
        """Polls for registered accounts that don't have syncs started."""
        while True:
            with session_scope() as db_session:
                unstarted_accounts = db_session.query(Account).filter(
                    Account.sync_state.is_(None)).all()
                if unstarted_accounts:
                    self.log.info(
                        'new accounts found',
                        account_ids=[acc.id for acc in unstarted_accounts])
                for account in unstarted_accounts:
                    self.start_sync(account.id)
            gevent.sleep(self.poll_interval)

    def start_sync(self, account_id):
        """
        Starts a sync for the account with the given account_id.
        If that account doesn't exist, does nothing.
        """
        with session_scope() as db_session:
            acc = db_session.query(Account).get(account_id)
            if acc is None:
                return 'No account with id {}'.format(account_id)
            fqdn = platform.node()
            self.log.info('Starting sync for account {0}'.format(
                acc.email_address))

            if acc.sync_host is not None and acc.sync_host != fqdn:
                return 'acc {0} is syncing on host {1}'.format(
                    acc.email_address, acc.sync_host)
            elif acc.id not in self.monitors:
                try:
                    acc.sync_lock()

                    monitor = self.monitor_cls_for[acc.provider](
                        acc.id, acc.namespace.id, acc.email_address,
                        acc.provider)
                    self.monitors[acc.id] = monitor
                    monitor.start()
                    # For Gmail accounts, also start contacts sync
                    if acc.provider == 'gmail':
                        contact_sync = ContactSync(acc.id)
                        self.contact_sync_monitors[acc.id] = contact_sync
                        contact_sync.start()
                    acc.start_sync(fqdn)
                    db_session.add(acc)
                    db_session.commit()
                    return 'OK sync started'
                except Exception as e:
                    self.log.error(e.message)
                    return 'ERROR error encountered: {0}'.format(e)
            else:
                return 'OK sync already started'

    def stop_sync(self, account_id):
        """
        Stops the sync for the account with given account_id.
        If that account doesn't exist, does nothing.

        """
        with session_scope() as db_session:
            acc = db_session.query(Account).get(account_id)
            if acc is None:
                return 'no account found for id {}'.format(account_id)
            fqdn = platform.node()
            if (not acc.id in self.monitors) or \
                    (not acc.sync_enabled):
                return 'OK sync stopped already'
            try:
                if acc.sync_host is None:
                    return 'Sync not running'

                assert acc.sync_host == fqdn, \
                    "sync host FQDN doesn't match: {0} <--> {1}" \
                    .format(acc.sync_host, fqdn)
                # XXX Can processing this command fail in some way?
                self.monitors[acc.id].inbox.put_nowait('shutdown')
                acc.stop_sync()
                db_session.add(acc)
                db_session.commit()
                acc.sync_unlock()
                del self.monitors[acc.id]
                # Also stop contacts sync (only relevant for Gmail
                # accounts)
                if acc.id in self.contact_sync_monitors:
                    del self.contact_sync_monitors[acc.id]
                return 'OK sync stopped'

            except Exception as e:
                return 'ERROR error encountered: {0}'.format(e)
