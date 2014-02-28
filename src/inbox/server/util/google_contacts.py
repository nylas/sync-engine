"""Provide Google contacts."""

import dateutil.parser
import datetime
import time

import gdata.auth
import gdata.contacts.client

from ..models.tables import Contact
from ..oauth import INSTALLED_CLIENT_ID, INSTALLED_CLIENT_SECRET, OAUTH_SCOPE
from ..oauth import get_new_token
from ..log import configure_logging

SOURCE_APP_NAME = 'InboxApp Contact Sync Engine'

class GoogleContactsProvider(object):
    """A utility class to fetch and parse Google contact data for the specified
    account using the Google Contacts API.

    Parameters
    ----------
    account: ..models.tables.ImapAccount
        The user account for which to fetch contact data.

    Attributes
    ----------
    google_client: gdata.contacts.client.ContactsClient
        Google API client to do the actual data fetching.
    log: logging.Logger
        Logging handler.
    """
    def __init__(self, account):
        self.account = account
        self.google_client = None
        self.log = configure_logging(account.id, 'googlecontacts')

    def _get_google_client(self):
        """Return the Google API client, creating it first if necessary."""
        if self.google_client is not None:
            return self.google_client
        try:
            access_token = get_new_token(
                    self.account.o_refresh_token)['access_token']
            two_legged_oauth_token = gdata.gauth.OAuth2Token(
                    client_id=INSTALLED_CLIENT_ID,
                    client_secret=INSTALLED_CLIENT_SECRET,
                    scope=OAUTH_SCOPE,
                    user_agent=SOURCE_APP_NAME,
                    access_token=access_token,
                    refresh_token=self.account.o_refresh_token)
            self.google_client = gdata.contacts.client.ContactsClient(
                    source=SOURCE_APP_NAME)
            self.google_client.auth_token = two_legged_oauth_token
            return self.google_client
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
        ..models.tables.Contact
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
            name = (google_contact.name.full_name.text if (google_contact.name
                and google_contact.name.full_name) else None)
            updated_at = (dateutil.parser.parse(google_contact.updated.text) if
                    google_contact.updated else None)
            email_address = (email_addresses[0].address if email_addresses else
                    None)
        except AttributeError, e:
            self.log.error('Something is wrong with contact: {0}'
                    .format(google_contact))
            raise e

        # TOFIX BUG
        # This rounds down the modified timestamp to not include fractional seconds.
        # There's an open patch for the MySQLdb, but I don't think it's worth adding just for this.
        # http://sourceforge.net/p/mysql-python/feature-requests/24/
        updated_at = datetime.datetime.fromtimestamp(
                time.mktime(updated_at.utctimetuple()))

        return Contact(imapaccount=self.account, source='local',
                name=name, updated_at=updated_at, email_address=email_address)

    def get_contacts(self, max_results=0):
        """Fetches and parses fresh contact data.

        Parameters
        ----------
        max_results: int, optional
            If nonzero, the maximum number of contact entries to fetch.

        Yields
        ------
        ..models.tables.Contact
            The contacts that have been updated since the last account sync.
        """
        query = gdata.contacts.client.ContactsQuery()
        # TODO(emfree): Implement batch fetching
        if max_results > 0:
            query.max_results = max_results
        if self.account.last_synced_contacts:
            query.updated_min = self.account.last_synced_contacts.isoformat()

        google_results = self._get_google_client().GetContacts(q=query).entry
        for result in google_results:
            yield self._parse_contact_result(result)
