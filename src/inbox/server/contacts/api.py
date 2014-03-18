"""API for Inbox contact sync service, exposed via ZeroRPC."""
from inbox.server.api import jsonify
from inbox.server.contacts.remote_sync import ContactSync
from inbox.server.log import get_logger
from inbox.server.models import session_scope
from inbox.server.models.tables import Contact, ImapAccount


class ContactService(object):
    """ ZeroRPC interface to the contacts service. """
    def __init__(self):
        self.log = get_logger()
        self.log.info('Updating contacts...')
        self.monitors = {}
        self.start_sync()

    @jsonify
    def start_sync(self, account_id=None):
        """Starts contact syncs for all accounts if account_id is None.
        If account_id is given, start sync only for that account.
        If account_id doesn't exist, do nothing.
        """
        results = {}
        with session_scope() as db_session:
            query = db_session.query(ImapAccount)
            if account_id is not None:
                account_id = int(account_id)
                query = query.filter_by(id=account_id)
            for account in query:
                if account.provider != 'Gmail':
                    # ONLY GMAIL CURRENTLY
                    results[account.id] = 'OK account type not supported'
                    continue
                contact_sync = ContactSync(account.id)
                self.monitors[account.id] = contact_sync
                results[account.id] = 'OK sync started'
                contact_sync.start()
        if account_id:
            if account_id in results:
                return results[account_id]
            else:
                return 'OK no such user'
        return results

    @jsonify
    def stop_sync(self, account_id=None):
        """Stops contact syncs for all accounts if account_id is None.
        If account_id is given, stop sync only for that account.
        If account_id doesn't exist, do nothing.
        """
        results = {}
        with session_scope as db_session:
            query = db_session.query(ImapAccount)
            if account_id is not None:
                account_id = int(account_id)
                query = query.filter_by(id=account_id)
            for account in query:
                if account.id in self.monitors:
                    del self.monitors[account.id]
                    results[account.id] = 'OK sync stopped'
                else:
                    results[account.id] = 'OK no sync for user'
        if account_id:
            if account_id in results:
                return results[account_id]
            else:
                return 'OK no such user'
        return results

    @jsonify
    def get(self, contact_id):
        """Get all data for an existing contact."""
        with session_scope() as db_session:
            contact = db_session.query(Contact).filter_by(id=contact_id).one()
            return contact.cereal()

    @jsonify
    def add(self, imapaccount_id, contact_info):
        """Add a new contact to the specified IMAP account. Returns the ID of
        the added contact."""
        with session_scope() as db_session:
            contact = Contact(imapaccount_id=imapaccount_id, source='local')
            contact.from_cereal(contact_info)
            db_session.add(contact)
            db_session.commit()
            self.log.info("Added contact {0}".format(contact.id))
            return contact.id

    def update(self, contact_id, contact_data):
        """Update data for an existing contact."""
        with session_scope() as db_session:
            contact = db_session.query(Contact).filter_by(id=contact_id).one()
            contact.from_cereal(contact_data)
            self.log.info("Updated contact {0}".format(contact.id))
            return 'OK'
