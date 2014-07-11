"""Provide Google contacts."""

import posixpath

import gdata.auth
import gdata.contacts.client

from inbox.log import get_logger
logger = get_logger()
from inbox.models.session import session_scope
from inbox.models import Contact
from inbox.models.backends.gmail import GmailAccount
from inbox.oauth import (GOOGLE_OAUTH_CLIENT_ID,
                              GOOGLE_OAUTH_CLIENT_SECRET, OAUTH_SCOPE)

SOURCE_APP_NAME = 'InboxApp Contact Sync Engine'


class GoogleContactsProvider(object):
    """A utility class to fetch and parse Google contact data for the specified
    account using the Google Contacts API.

    Parameters
    ----------
    db_session: sqlalchemy.orm.session.Session
        Database session.

    account: inbox.models.gmail.GmailAccount
        The user account for which to fetch contact data.

    Attributes
    ----------
    google_client: gdata.contacts.client.ContactsClient
        Google API client to do the actual data fetching.
    log: logging.Logger
        Logging handler.
    """
    PROVIDER_NAME = 'google'

    def __init__(self, account_id):
        self.account_id = account_id
        self.log = logger.new(account_id=account_id, component='contacts sync',
                              provider=self.PROVIDER_NAME)

    def _get_google_client(self):
        """Return the Google API client."""
        # TODO(emfree) figure out a better strategy for refreshing OAuth
        # credentials as needed
        with session_scope() as db_session:
            try:
                account = db_session.query(GmailAccount).get(self.account_id)
                two_legged_oauth_token = gdata.gauth.OAuth2Token(
                    client_id=GOOGLE_OAUTH_CLIENT_ID,
                    client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
                    scope=OAUTH_SCOPE,
                    user_agent=SOURCE_APP_NAME,
                    access_token=account.access_token,
                    refresh_token=account.refresh_token)
                google_client = gdata.contacts.client.ContactsClient(
                    source=SOURCE_APP_NAME)
                google_client.auth_token = two_legged_oauth_token
                return google_client
            except gdata.client.BadAuthentication:
                self.log.error('Invalid user credentials given')
                return None

    def _parse_contact_result(self, google_contact):
        """Constructs a Contact object from a Google contact entry.

        Parameters
        ----------
        google_contact: gdata.contacts.entry.ContactEntry
            The Google contact entry to parse.

        Returns
        -------
        ..models.tables.base.Contact
            A corresponding Inbox Contact instance.

        Raises
        ------
        AttributeError
           If the contact data could not be parsed correctly.
        """
        email_addresses = [email for email in google_contact.email if
                           email.primary]
        if email_addresses and len(email_addresses) > 1:
            self.log.error("Should not have more than one email per entry! {0}"
                           .format(email_addresses))
        try:
            # The id.text field of a ContactEntry object takes the form
            # 'http://www.google.com/m8/feeds/contacts/<useremail>/base/<uid>'.
            # We only want the <uid> part.
            raw_google_id = google_contact.id.text
            _, g_id = posixpath.split(raw_google_id)
            name = (google_contact.name.full_name.text if (google_contact.name
                    and google_contact.name.full_name) else None)
            email_address = (email_addresses[0].address if email_addresses else
                             None)

            # The entirety of the raw contact data in XML string
            # representation.
            raw_data = google_contact.to_string()
        except AttributeError, e:
            self.log.error('Something is wrong with contact',
                           contact=google_contact)
            raise e

        deleted = google_contact.deleted is not None

        return Contact(account_id=self.account_id, source='remote',
                       uid=g_id, name=name, provider_name=self.PROVIDER_NAME,
                       email_address=email_address, deleted=deleted,
                       raw_data=raw_data)

    def get_contacts(self, sync_from_time=None, max_results=100000):
        """Fetches and parses fresh contact data.

        Parameters
        ----------
        sync_from_time: str, optional
            A time in ISO 8601 format: If not None, fetch data for contacts
            that have been updated since this time. Otherwise fetch all contact
            data.
        max_results: int, optional
            The maximum number of contact entries to fetch.

        Yields
        ------
        ..models.tables.base.Contact
            The contacts that have been updated since the last account sync.
        """
        query = gdata.contacts.client.ContactsQuery()
        # TODO(emfree): Implement batch fetching
        # Note: The Google contacts API will only return 25 results if
        # query.max_results is not explicitly set, so have to set it to a large
        # number by default.
        query.max_results = max_results
        query.updated_min = sync_from_time
        query.showdeleted = True
        google_client = self._get_google_client()
        if google_client is None:
            # Return an empty generator if we couldn't create an API client
            return
        for result in google_client.GetContacts(q=query).entry:
            yield self._parse_contact_result(result)
