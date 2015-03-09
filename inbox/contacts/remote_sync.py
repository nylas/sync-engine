from datetime import datetime
from collections import Counter

from sqlalchemy.orm.exc import NoResultFound

from inbox.log import get_logger
logger = get_logger()
from inbox.models import Contact, Account
from inbox.sync.base_sync import BaseSyncMonitor
from inbox.contacts.google import GoogleContactsProvider
from inbox.contacts.icloud import ICloudContactsProvider
from inbox.util.debug import bind_context
from inbox.models.session import session_scope
from inbox.basicauth import ValidationError


CONTACT_SYNC_PROVIDER_MAP = {'gmail': GoogleContactsProvider,
                             'icloud': ICloudContactsProvider}

CONTACT_SYNC_FOLDER_ID = -1
CONTACT_SYNC_FOLDER_NAME = 'Contacts'


class ContactSync(BaseSyncMonitor):
    """
    Per-account contact sync engine.

    Parameters
    ----------
    account_id: int
        The ID for the user account for which to fetch contact data.

    poll_frequency: int
        In seconds, the polling frequency for querying the contacts provider
        for updates.

    Attributes
    ---------
    log: logging.Logger
        Logging handler.

    """
    def __init__(self, email_address, provider_name, account_id, namespace_id,
                 poll_frequency=300):
        bind_context(self, 'contactsync', account_id)
        self.log = logger.new(account_id=account_id, component='contact sync')
        self.log.info('Begin syncing contacts...')

        self.folder_name = CONTACT_SYNC_FOLDER_NAME
        self.email_address = email_address
        self.provider_name = provider_name

        provider_cls = CONTACT_SYNC_PROVIDER_MAP[self.provider_name]
        self.provider = provider_cls(account_id, namespace_id)

        BaseSyncMonitor.__init__(self,
                                 account_id,
                                 namespace_id,
                                 CONTACT_SYNC_FOLDER_ID,
                                 poll_frequency=poll_frequency,
                                 retry_fail_classes=[ValidationError])

    def sync(self):
        """Query a remote provider for updates and persist them to the
        database. This function runs every `self.poll_frequency`.

        """
        # Grab timestamp so next sync gets deltas from now
        sync_timestamp = datetime.utcnow()

        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            last_sync_dt = account.last_synced_contacts

            all_contacts = self.provider.get_items(sync_from_dt=last_sync_dt)

            # Do a batch insertion of every 100 contact objects
            change_counter = Counter()
            for new_contact in all_contacts:
                new_contact.namespace = account.namespace
                assert new_contact.uid is not None, \
                    'Got remote item with null uid'
                assert isinstance(new_contact.uid, basestring)

                try:
                    existing_contact = db_session.query(Contact).filter(
                        Contact.namespace == account.namespace,
                        Contact.provider_name == self.provider.PROVIDER_NAME,
                        Contact.uid == new_contact.uid).one()

                    # If the remote item was deleted, purge the corresponding
                    # database entries.
                    if new_contact.deleted:
                        db_session.delete(existing_contact)
                        change_counter['deleted'] += 1
                    else:
                        # Update fields in our old item with the new.
                        # Don't save the newly returned item to the database.
                        existing_contact.merge_from(new_contact)
                        change_counter['updated'] += 1

                except NoResultFound:
                    # We didn't know about this before! Add this item.
                    db_session.add(new_contact)
                    change_counter['added'] += 1

                # Flush every 100 objects for perf
                if sum(change_counter.values()) % 100:
                    db_session.flush()

        # Update last sync
        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            account.last_synced_contacts = sync_timestamp

        self.log.info('sync', added=change_counter['added'],
                      updated=change_counter['updated'],
                      deleted=change_counter['deleted'])
