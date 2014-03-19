import datetime

import gevent

from inbox.server.models import session_scope
from inbox.server.models.tables.base import Contact, Account
from inbox.server.log import configure_contacts_logging, get_logger
from inbox.server.contacts.google import GoogleContactsProvider
from inbox.util.misc import or_none

log = get_logger()


class ContactSync(gevent.Greenlet):
    """Per-account contact sync engine.

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
    def __init__(self, account_id, poll_frequency=300):
        self.account_id = account_id
        self.poll_frequency = poll_frequency
        self.log = configure_contacts_logging(account_id)
        self.log.info('Begin syncing contacts...')

        gevent.Greenlet.__init__(self)

    def _run(self):
        contacts_provider = GoogleContactsProvider(self.account_id)
        while True:
            poll(self.account_id, contacts_provider)
            gevent.sleep(self.poll_frequency)


def poll(account_id, provider):
    """Query a remote contacts provider for updates and persist them to the
    database.

    Parameters
    ----------
    account_id: int
        ID for the account whose contacts should be queried.
    db_session: sqlalchemy.orm.session.Session
        Database session

    provider: .util.google_contacts.GoogleContactsProvider
        Interface to the remote contact data provider.
    """
    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)

        # Contact data reflecting any local modifications since the last sync
        # with the remote provider.
        local_contacts = db_session.query(Contact).filter_by(
            source='local', account=account).all()
        # Snapshot of contact data from immediately after last sync.
        cached_contacts = db_session.query(Contact).filter_by(
            source='remote', account=account).all()
        log.info('Query: have {0} contacts, {1} cached.'.format(
            len(local_contacts), len(cached_contacts)))

        cached_contact_dict = {contact.g_id: contact for contact in
                               cached_contacts}
        local_contact_dict = {contact.g_id: contact for contact in
                              local_contacts}

        num_added_contacts = 0
        num_updated_contacts = 0
        last_sync = or_none(account.last_synced_contacts,
                            datetime.datetime.isoformat)
        to_commit = []
        for remote_contact in provider.get_contacts(last_sync):
            remote_contact.account = account
            assert remote_contact.g_id is not None, \
                'Got remote contact with null g_id'
            cached_contact = cached_contact_dict.get(remote_contact.g_id)
            local_contact = local_contact_dict.get(remote_contact.g_id)
            if cached_contact is not None:
                # The provider gave an update to a contact we already have.
                if local_contact is not None:
                    try:
                        # Attempt to merge remote updates into local_contact
                        merge(cached_contact, remote_contact, local_contact)
                        # And update cached_contact to reflect both local and
                        # remote updates
                        cached_contact.copy_from(local_contact)
                    except MergeError:
                        log.error('Conflicting local and remote updates to '
                                  'contact.\nLocal: {0}\ncached: {1}\n '
                                  'remote: {2}'.format(local_contact,
                                                       cached_contact,
                                                       remote_contact))
                        # TODO(emfree): Come up with a strategy for handling
                        # merge conflicts. For now, just don't update if there
                        # is a conflict.
                        continue
                else:
                    log.warning('Contact {0} already present as remote but '
                                'not local contact'.format(cached_contact))
                    cached_contact.copy_from(remote_contact)
                num_updated_contacts += 1
            else:
                # This is a new contact, create both local and remote DB
                # entries.
                local_contact = Contact()
                local_contact.copy_from(remote_contact)
                local_contact.source = 'local'
                to_commit.append(local_contact)
                to_commit.append(remote_contact)
                num_added_contacts += 1

        account.last_synced_contacts = datetime.datetime.now()

        log.info('Added {0} contacts.'.format(num_added_contacts))
        log.info('Updated {0} contacts.'.format(num_updated_contacts))

        db_session.add_all(to_commit)
        db_session.commit()


def merge(base, remote, dest):
    """Merge changes from remote into dest if there are no conflicting updates
    to remote and dest relative to base.

    Parameters
    ----------
    base, remote, dest: .models.tables.Contact

    Raises
    ------
    MergError
        If there is a conflict.
    """
    # This must be updated when new fields are added to the Contact class.
    attributes = ['name', 'email_address']
    for attr_name in attributes:
        base_attr = getattr(base, attr_name)
        remote_attr = getattr(remote, attr_name)
        dest_attr = getattr(dest, attr_name)
        if base_attr != remote_attr != dest_attr != base_attr:
            raise MergeError('Conflicting updates to contacts {0}, {1} from '
                             'base {2}'.format(remote, dest, base))
    # No conflicts, can merge
    for attr_name in attributes:
        base_attr = getattr(base, attr_name)
        remote_attr = getattr(remote, attr_name)
        if base_attr != remote_attr:
            setattr(dest, attr_name, remote_attr)


class MergeError(Exception):
    pass
