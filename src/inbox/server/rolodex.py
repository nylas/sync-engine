import copy
import datetime

from .models import session_scope
from .models.tables import Contact, ImapAccount
from .log import configure_rolodex_logging, get_logger
from .util.google_contacts import GoogleContactsProvider
log = get_logger()

def rolodex_sync(db_session, account):
    log = configure_rolodex_logging(account.id)
    log.info('Begin syncing contacts...')

    # ONLY GMAIL CURRENTLY
    if account.provider != 'Gmail':
        log.error('Inbox currently supports Gmail only!')
        return
    else:
        contacts_provider = GoogleContactsProvider(account)

    existing_contacts = db_session.query(Contact).filter_by(
            source='local', imapaccount=account).all()
    cached_contacts = db_session.query(Contact).filter_by(
            source='remote', imapaccount=account).all()

    log.info('Query: have {0} contacts, {1} cached.'.format(
        len(existing_contacts), len(cached_contacts)))

    contact_dict = {}
    for contact in existing_contacts:
        contact_dict[contact.g_id] = contact

    cached_dict = {}
    for contact in cached_contacts:
        cached_dict[contact.g_id] = contact

    to_commit = []

    for c in contacts_provider.get_contacts():
        # STOPSHIP(emfree): c.g_id is never set
        if c.g_id in contact_dict:
            existing = contact_dict[c.g_id]

            if c.g_id in cached_dict:
                # now we can get a diff and merge
                cached = cached_dict[c.g_id]

                if cached.name != c.name:
                    existing.name = c.name
                if cached.email_address != c.email_address:
                    existing.email_address = c.email_address

            else:
                # no diff, just overwrite it
                existing = contact_dict[c.g_id]
                existing.name = c.name
                existing.email_address = c.email_address

        else:
            # doesn't exist yet, add both remote and local
            cached = copy.deepcopy(c)
            cached.source = 'remote'

            to_commit.append(c)
            to_commit.append(cached)

    account.last_synced_contacts = datetime.datetime.now()

    db_session.add_all(to_commit)
    db_session.commit()

    log.info('Added {0} contacts.'.format(len(to_commit)))

class ContactSync(object):
    """ ZeroRPC interface to syncing. """
    def __init__(self):
        log.info('Updating contacts...')
        with session_scope() as db_session:
            for account in db_session.query(ImapAccount):
                rolodex_sync(db_session, account)
