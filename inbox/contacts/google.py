"""Provide Google contacts."""

import posixpath

import gdata.auth
import gdata.client
import gdata.contacts.client

from inbox.log import get_logger
logger = get_logger()
from inbox.basicauth import ConnectionError, ValidationError, PermissionsError
from inbox.basicauth import OAuthError
from inbox.models.session import session_scope
from inbox.models import Contact
from inbox.models.backends.gmail import GmailAccount
from inbox.auth.gmail import (OAUTH_CLIENT_ID,
                              OAUTH_CLIENT_SECRET,
                              OAUTH_SCOPE)
from inbox.sync.base_sync_provider import BaseSyncProvider

SOURCE_APP_NAME = 'InboxApp Contact Sync Engine'


class GoogleContactsProvider(BaseSyncProvider):
    """
    A utility class to fetch and parse Google contact data for the specified
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

    def __init__(self, account_id, namespace_id):
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.log = logger.new(account_id=account_id, component='contacts sync',
                              provider=self.PROVIDER_NAME)

    def _get_google_client(self):
        """Return the Google API client."""
        # TODO(emfree) figure out a better strategy for refreshing OAuth
        # credentials as needed
        with session_scope() as db_session:
            try:
                account = db_session.query(GmailAccount).get(self.account_id)
                client_id = account.client_id or OAUTH_CLIENT_ID
                client_secret = (account.client_secret or
                                 OAUTH_CLIENT_SECRET)
                two_legged_oauth_token = gdata.gauth.OAuth2Token(
                    client_id=client_id,
                    client_secret=client_secret,
                    scope=OAUTH_SCOPE,
                    user_agent=SOURCE_APP_NAME,
                    access_token=account.access_token,
                    refresh_token=account.refresh_token)
                google_client = gdata.contacts.client.ContactsClient(
                    source=SOURCE_APP_NAME)
                google_client.auth_token = two_legged_oauth_token
                return google_client
            except (gdata.client.BadAuthentication, OAuthError):
                self.log.info('Invalid user credentials given')
                account.sync_state = 'invalid'
                db_session.add(account)
                db_session.commit()
                raise ValidationError
            except ConnectionError:
                self.log.error('Connection error')
                account.sync_state = 'connerror'
                db_session.add(account)
                db_session.commit()
                raise

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

        return Contact(namespace_id=self.namespace_id, source='remote',
                       uid=g_id, name=name, provider_name=self.PROVIDER_NAME,
                       email_address=email_address, deleted=deleted,
                       raw_data=raw_data)

    def get_items(self, sync_from_time=None, max_results=100000):
        """
        Fetches and parses fresh contact data.

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

        Raises
        ------
        ValidationError, PermissionsError
            If no data could be fetched because of invalid credentials or
            insufficient permissions, respectively.

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
        try:
            results = google_client.GetContacts(q=query).entry
            return [self._parse_contact_result(result) for result in results]
        except gdata.client.RequestError as e:
            # This is nearly always because we authed with Google OAuth
            # credentials for which the contacts API is not enabled.
            self.log.info('contact sync request failure', message=e)
            raise PermissionsError('contact sync request failure')
