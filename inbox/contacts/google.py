"""Provide Google contacts."""
import posixpath
import random
import gevent
from datetime import datetime

import gdata.auth
import gdata.client
import gdata.contacts.client

from nylas.logging import get_logger
logger = get_logger()
from inbox.basicauth import ConnectionError, ValidationError
from inbox.basicauth import OAuthError
from inbox.models.session import session_scope
from inbox.models import Contact
from inbox.models.backends.gmail import GmailAccount, g_token_manager
from inbox.models.backends.gmail import GmailAuthCredentials

SOURCE_APP_NAME = 'Nylas Sync Engine'


class GoogleContactsProvider(object):
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

    def _get_google_client(self, retry_conn_errors=True):
        """Return the Google API client."""
        # TODO(emfree) figure out a better strategy for refreshing OAuth
        # credentials as needed
        with session_scope(self.namespace_id) as db_session:
            try:
                account = db_session.query(GmailAccount).get(self.account_id)
                access_token, auth_creds_id = \
                    g_token_manager.get_token_and_auth_creds_id_for_contacts(
                        account)
                auth_creds = db_session.query(GmailAuthCredentials) \
                    .get(auth_creds_id)

                two_legged_oauth_token = gdata.gauth.OAuth2Token(
                    client_id=auth_creds.client_id,
                    client_secret=auth_creds.client_secret,
                    scope=auth_creds.scopes,  # FIXME: string not list?
                    user_agent=SOURCE_APP_NAME,
                    access_token=access_token,
                    refresh_token=auth_creds.refresh_token)
                google_client = gdata.contacts.client.ContactsClient(
                    source=SOURCE_APP_NAME)
                google_client.auth_token = two_legged_oauth_token
                return google_client
            except (gdata.client.BadAuthentication,
                    gdata.client.Unauthorized, OAuthError):

                if not retry_conn_errors:  # end of the line
                    raise ValidationError

                # If there are no valid refresh_tokens, will raise an
                # OAuthError, stopping the sync
                g_token_manager.get_token_for_contacts(
                    account, force_refresh=True)
                return self._google_client(retry_conn_errors=False)

            except ConnectionError:
                self.log.error('Connection error')
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
            A corresponding Nylas Contact instance.

        Raises
        ------
        AttributeError
           If the contact data could not be parsed correctly.
        """
        email_addresses = [email for email in google_contact.email if
                           email.primary]
        if email_addresses and len(email_addresses) > 1:
            self.log.error("Should not have more than one email per entry!",
                           num_email=len(email_addresses))

        try:
            # The id.text field of a ContactEntry object takes the form
            # 'http://www.google.com/m8/feeds/contacts/<useremail>/base/<uid>'.
            # We only want the <uid> part.
            raw_google_id = google_contact.id.text
            _, g_id = posixpath.split(raw_google_id)
            name = (google_contact.name.full_name.text
                    if (google_contact.name and google_contact.name.full_name)
                    else None)
            email_address = (email_addresses[0].address if email_addresses else
                             None)

            # The entirety of the raw contact data in XML string
            # representation.
            raw_data = google_contact.to_string()
        except AttributeError as e:
            self.log.error('Something is wrong with contact',
                           contact=google_contact)
            raise e

        deleted = google_contact.deleted is not None

        return Contact(namespace_id=self.namespace_id, uid=g_id, name=name,
                       provider_name=self.PROVIDER_NAME,
                       email_address=email_address, deleted=deleted,
                       raw_data=raw_data)

    def get_items(self, sync_from_dt=None, max_results=100000):
        """
        Fetches and parses fresh contact data.

        Parameters
        ----------
        sync_from_dt: datetime, optional
            If given, fetch contacts that have been updated since this time.
            Otherwise fetch all contacts
        max_results: int, optional
            The maximum number of contact entries to fetch.

        Yields
        ------
        ..models.tables.base.Contact
            The contacts that have been updated since the last account sync.

        Raises
        ------
        ValidationError
            If no data could be fetched because of invalid credentials or
            insufficient permissions, respectively.

        """
        query = gdata.contacts.client.ContactsQuery()
        # TODO(emfree): Implement batch fetching
        # Note: The Google contacts API will only return 25 results if
        # query.max_results is not explicitly set, so have to set it to a large
        # number by default.
        query.max_results = max_results
        if sync_from_dt:
            query.updated_min = datetime.isoformat(sync_from_dt) + 'Z'
        query.showdeleted = True
        while True:
            try:
                google_client = self._get_google_client()
                results = google_client.GetContacts(q=query).entry
                return [self._parse_contact_result(result) for result in
                        results]
            except gdata.client.RequestError as e:
                if e.status == 503:
                    self.log.info('Ran into Google bot detection. Sleeping.',
                                  message=e)
                    gevent.sleep(5 * 60 + random.randrange(0, 60))
                else:
                    self.log.info('contact sync request failure; retrying',
                                  message=e)
                    gevent.sleep(30 + random.randrange(0, 60))
            except gdata.client.Unauthorized:
                self.log.warning(
                    'Invalid access token; refreshing and retrying')
                # Raises an OAuth error if no valid token exists
                with session_scope(self.namespace_id) as db_session:
                    account = db_session.query(GmailAccount).get(
                        self.account_id)
                    g_token_manager.get_token_for_contacts(
                        account, force_refresh=True)
