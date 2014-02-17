import gdata.contacts.data
import gdata.contacts.client
import gdata.auth
import dateutil.parser
import datetime
import time

from .oauth import INSTALLED_CLIENT_ID, INSTALLED_CLIENT_SECRET, OAUTH_SCOPE
from .oauth import get_new_token

from .models import session_scope
from .models.tables import Contact, ImapAccount
from .log import configure_rolodex_logging, get_logger
log = get_logger()

SOURCE_APP_NAME = 'InboxApp Contact Sync Engine'

def rolodex_sync(db_session, account):
    log = configure_rolodex_logging(account.id)
    log.info("Begin syncing contacts...")

    # ONLY GMAIL CURRENTLY
    if account.provider != 'Gmail':
        log.info('Inbox currently supports Gmail only!')
        return

    existing_contacts = db_session.query(Contact).filter_by(
            source = "local", imapaccount=account).all()
    cached_contacts = db_session.query(Contact).filter_by(
            source = "remote", imapaccount=account).all()

    log.info("Query: have {0} contacts, {1} cached.".format(
        len(existing_contacts), len(cached_contacts)))

    contact_dict = {}
    for contact in existing_contacts:
        contact_dict[contact.g_id] = contact

    cached_dict = {}
    for contact in cached_contacts:
        cached_dict[contact.g_id] = contact

    try:
        access_token = get_new_token(
                account.o_refresh_token)['access_token']
        two_legged_oauth_token = gdata.gauth.OAuth2Token(
                    client_id = INSTALLED_CLIENT_ID,
                    client_secret = INSTALLED_CLIENT_SECRET,
                    scope = OAUTH_SCOPE,
                    user_agent =SOURCE_APP_NAME,
                    access_token=access_token,
                    refresh_token=account.o_refresh_token,
                )
        gd_client = gdata.contacts.client.ContactsClient(source=SOURCE_APP_NAME)
        gd_client.auth_token = two_legged_oauth_token
        query = gdata.contacts.client.ContactsQuery()
        if account.last_synced_contacts:
            query.updated_min = account.last_synced_contacts.isoformat()

        # TODO should probably fetch in batches instead of at once
        query.max_results = 25000

    except gdata.client.BadAuthentication:
        log.error('Invalid user credentials given.')
        return

    to_commit = []

    for g_contact in gd_client.GetContacts(q = query).entry:
        email_addresses = filter(lambda email: email.primary, g_contact.email)
        if email_addresses and len(email_addresses) > 1:
            log.error("Should not have more than one email per entry! {0}".format(email_addresses))
        # Punt on phone numbers right now
        # if g_contact.phone_number and len(g_contact.phone_number) > 1:
        #     log.error("Should not have more than one phone number per entry! {0}".format(g_contact.phone_number))

        try:
            google_result = {
                "name": g_contact.name.full_name.text if (g_contact.name and g_contact.name.full_name) else None,
                "updated_at": dateutil.parser.parse(g_contact.updated.text) if g_contact.updated else None,
                "email_address": email_addresses[0].address if email_addresses else None,
                # "phone_number": str(g_contact.phone_number[0].text) if g_contact.phone_number else None,
            }
        except AttributeError, e:
            log.error("Something weird with contact: {0}".format(g_contact))
            raise e

        # TOFIX BUG
        # This rounds down the modified timestamp to not include fractional seconds.
        # There's an open patch for the MySQLdb, but I don't think it's worth adding just for this.
        # http://sourceforge.net/p/mysql-python/feature-requests/24/
        google_result['updated_at'] = datetime.datetime.fromtimestamp(
                                            time.mktime(google_result['updated_at'].utctimetuple()))

        # make an object out of the google result
        c = Contact(imapaccount = account, source='local', **google_result)

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
            cached = Contact(imapaccount = account, **google_result)
            cached.source = "remote"

            to_commit.append(c)
            to_commit.append(cached)

    account.last_synced_contacts = datetime.datetime.now()

    db_session.add_all(to_commit)
    db_session.commit()

    log.info("Added {0} contacts.".format(len(to_commit)))

class ContactSync(object):
    """ ZeroRPC interface to syncing. """
    def __init__(self):
        log.info("Updating contacts...")
        with session_scope() as db_session:
            for account in db_session.query(ImapAccount):
                rolodex_sync(db_session, account)
