import gdata.contacts.data
import gdata.contacts.client
import gdata.auth
import dateutil.parser
import datetime
from google_oauth import GOOGLE_CONSUMER_KEY, GOOGLE_CONSUMER_SECRET, OAUTH_SCOPE

from .models import db_session, Contact, IMAPAccount
from .log import get_logger; log = get_logger()

SOURCE_APP_NAME = 'InboxApp Sync Server'


class Rolodex(object):
    """docstring for Rolodex"""
    def __init__(self, account):
        self.account = account
        self.email_address = account.email_address
        self.oauth_token = account.o_access_token


    def sync(self):
        log.info("Begin syncing contacts...")

        existing_contacts = db_session.query(Contact).filter_by(source = "local", imapaccount=self.account).all()
        cached_contacts = db_session.query(Contact).filter_by(source = "remote", imapaccount=self.account).all()

        log.info("Query: have {0} contacts, {1} cached.".format(len(existing_contacts), len(cached_contacts)))

        contact_dict = {}
        for contact in existing_contacts:
            contact_dict[contact.g_id] = contact

        cached_dict = {}
        for contact in cached_contacts:
            cached_dict[contact.g_id] = contact

        try:
            two_legged_oauth_token = gdata.gauth.OAuth2Token(
                      client_id = GOOGLE_CONSUMER_KEY,
                      client_secret = GOOGLE_CONSUMER_SECRET,
                      scope = OAUTH_SCOPE,
                      user_agent =SOURCE_APP_NAME,
                      access_token=self.account.o_access_token,
                      refresh_token=self.account.o_refresh_token,
                    )
            gd_client = gdata.contacts.client.ContactsClient(source=SOURCE_APP_NAME)
            gd_client.auth_token = two_legged_oauth_token
            query = gdata.contacts.client.ContactsQuery()
            if self.account.last_synced_contacts:
                query.updated_min = self.account.last_synced_contacts.isoformat()

            # TODO should probably fetch in batches instead of at once
            query.max_results = 25000

        except gdata.client.BadAuthentication:
            print 'Invalid user credentials given.'
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
                print "Something weird with contact:", g_contact
                raise e

            # make an object out of the google result
            c = Contact(imapaccount = self.account, source='local', **google_result)

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
                cached = Contact(imapaccount = self.account, **google_result)
                cached.source = "remote"

                to_commit.append(c)
                to_commit.append(cached)

        self.account.last_synced_contacts = datetime.datetime.now()

        db_session.add_all(to_commit)
        db_session.commit()

        log.info("Added {0} contacts.".format(len(to_commit)))




class ContactSync:
    """ ZeroRPC interface to syncing. """
    def __init__(self):
        log.info("Updating contacts...")
        for account in db_session.query(IMAPAccount):
            self.start_sync(account)

    def start_sync(self, account):
        r = Rolodex(account)
        r.sync()



