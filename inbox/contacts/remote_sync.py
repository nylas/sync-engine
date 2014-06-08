import datetime
from collections import Counter

import gevent

from inbox.models import session_scope
from inbox.models.tables.base import Contact, Account
from inbox.log import (configure_contacts_logging, get_logger,
                              log_uncaught_errors)
from inbox.contacts.google import GoogleContactsProvider
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
        return log_uncaught_errors(self._run_impl, self.log)()

    def _run_impl(self):
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

    provider: Interface to the remote contact data provider.
        Must have a PROVIDER_NAME attribute and implement the get_contacts()
        method.
    """
    provider_name = provider.PROVIDER_NAME
    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        change_counter = Counter()
        last_sync = or_none(account.last_synced_contacts,
                            datetime.datetime.isoformat)
        to_commit = []
        for remote_contact in provider.get_contacts(last_sync):
            remote_contact.account = account
            assert remote_contact.uid is not None, \
                'Got remote contact with null uid'
            assert isinstance(remote_contact.uid, str)
            matching_contacts = db_session.query(Contact).filter(
                Contact.account == account,
                Contact.provider_name == provider_name,
                Contact.uid == remote_contact.uid)
            # Snapshot of contact data from immediately after last sync:
            cached_contact = matching_contacts. \
                filter(Contact.source == 'remote').first()
            # Contact data reflecting any local modifications since the last
            # sync with the remote provider:
            local_contact = matching_contacts. \
                filter(Contact.source == 'local').first()
            # If the remote contact was deleted, purge the corresponding
            # database entries.
            if remote_contact.deleted:
                if cached_contact is not None:
                    db_session.delete(cached_contact)
                    change_counter['deleted'] += 1
                if local_contact is not None:
                    db_session.delete(local_contact)
                continue
            # Otherwise, update the database.
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
                change_counter['updated'] += 1
            else:
                # This is a new contact, create both local and remote DB
                # entries.
                local_contact = Contact()
                local_contact.copy_from(remote_contact)
                local_contact.source = 'local'
                to_commit.append(local_contact)
                to_commit.append(remote_contact)
                change_counter['added'] += 1

        account.last_synced_contacts = datetime.datetime.now()

        log.info('Added {0} contacts.'.format(change_counter['added']))
        log.info('Updated {0} contacts.'.format(change_counter['updated']))
        log.info('Deleted {0} contacts.'.format(change_counter['deleted']))

        db_session.add_all(to_commit)
        db_session.commit()


def merge(base, remote, dest):
    """Merge changes from remote into dest if there are no conflicting updates
    to remote and dest relative to base.

    Parameters
    ----------
    base, remote, dest: .models.tables.base.Contact

    Raises
    ------
    MergeError
        If there is a conflict.
    """
    # This must be updated when new fields are added to the Contact class.
    attributes = ['name', 'email_address', 'raw_data']
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
