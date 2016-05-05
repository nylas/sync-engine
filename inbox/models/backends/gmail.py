from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from random import shuffle

from sqlalchemy import Boolean, Column, BigInteger, String, ForeignKey
from sqlalchemy import DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.session import object_session
from sqlalchemy.ext.hybrid import hybrid_property

from inbox.basicauth import ConnectionError, OAuthError
from inbox.models.session import session_scope
from inbox.models.backends.imap import ImapAccount
from inbox.models.backends.oauth import OAuthAccount
from inbox.models.base import MailSyncBase
from inbox.models.secret import Secret
from inbox.models.mixins import UpdatedAtMixin, DeletedAtMixin

from nylas.logging import get_logger
log = get_logger()

PROVIDER = 'gmail'

GOOGLE_CALENDAR_SCOPE = 'https://www.googleapis.com/auth/calendar'
GOOGLE_EMAIL_SCOPE = 'https://mail.google.com/'
GOOGLE_CONTACTS_SCOPE = 'https://www.google.com/m8/feeds'


# Google token named tuple - only used in this file.
# NOTE: we only keep track of the auth_credentials id because
# we need it for contacts sync (which is unfortunate). If that ever
# changes, we should remove auth_creds from GToken.
GToken = namedtuple('GToken',
                    'value expiration scopes client_id auth_creds_id')


class GTokenManager(object):
    """
    A separate class for managing access tokens from Google accounts.
    Necessary because google access tokens are only valid for certain
    scopes.
    Based off of TokenManager in inbox/backends/oauth.py

    """

    def __init__(self):
        self._tokens = defaultdict(dict)

    def _get_token(self, account, scope, force_refresh=False):
        if not force_refresh:
            try:
                gtoken = self._tokens[account.id][scope]
                if datetime.utcnow() < gtoken.expiration:
                    return gtoken
            except KeyError:
                pass

        # If we find invalid GmailAuthCredentials while trying to
        # get a new token, we mark them as invalid. We want to make
        # sure we commit those changes to the database before we
        # actually throw an error.
        try:
            gtoken = account.new_token(scope)
        except (ConnectionError, OAuthError):
            if object_session(account):
                object_session(account).commit()
            else:
                with session_scope(account.id) as db_session:
                    db_session.merge(account)
                    db_session.commit()
            raise

        self.cache_token(account, gtoken)
        return gtoken

    def get_token(self, account, scope, force_refresh=False):
        gtoken = self._get_token(account, scope, force_refresh=force_refresh)
        return gtoken.value

    def get_token_for_email(self, account, force_refresh=False):
        return self.get_token(account, GOOGLE_EMAIL_SCOPE, force_refresh)

    def get_token_for_calendars(self, account, force_refresh=False):
        return self.get_token(account, GOOGLE_CALENDAR_SCOPE, force_refresh)

    def get_token_for_contacts(self, account, force_refresh=False):
        return self.get_token(account, GOOGLE_CONTACTS_SCOPE, force_refresh)

    def get_token_and_auth_creds_id(self, account, scope, force_refresh=False):
        """Just for Contacts sync..."""
        gtoken = self._get_token(account, scope, force_refresh=force_refresh)
        return gtoken.value, gtoken.auth_creds_id

    def get_token_and_auth_creds_id_for_contacts(self, account,
                                                 force_refresh=False):
        return self.get_token_and_auth_creds_id(
            account, GOOGLE_CONTACTS_SCOPE, force_refresh)

    def cache_token(self, account, gtoken):
        for scope in gtoken.scopes:
            self._tokens[account.id][scope] = gtoken

    def clear_cache(self, account):
        self._tokens[account.id] = {}

    def get_token_for_calendars_restrict_ids(self, account, client_ids,
                                             force_refresh=False):
        """
        For the given account, returns an access token that's associated
        with a client id from the given list of client_ids.

        """
        scope = GOOGLE_CALENDAR_SCOPE
        if not force_refresh:
            try:
                gtoken = self._tokens[account.id][scope]
                if gtoken.client_id in client_ids:
                    return gtoken.value
            except KeyError:
                pass

        # Need to get access token for specific client_id/client_secret pair
        try:
            gtoken = account.new_token(scope, client_ids=client_ids)
        except (ConnectionError, OAuthError):
            object_session(account).commit()
            raise

        self.cache_token(account, gtoken)
        return gtoken.value


g_token_manager = GTokenManager()


class GmailAccount(OAuthAccount, ImapAccount):
    id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    __mapper_args__ = {'polymorphic_identity': 'gmailaccount'}

    # STOPSHIP(emfree) store these either as secrets or as properties of the
    # developer app.
    client_id = Column(String(256))
    client_secret = Column(String(256))
    scope = Column(String(512))
    access_type = Column(String(64))
    family_name = Column(String(256))
    given_name = Column(String(256))
    gender = Column(String(16))
    g_id = Column(String(32))  # `id`
    g_id_token = Column(String(1024))  # `id_token`
    g_user_id = Column(String(32))  # `user_id`
    link = Column(String(256))
    locale = Column(String(8))
    picture = Column(String(1024))
    home_domain = Column(String(256))

    # for google push notifications:
    last_calendar_list_sync = Column(DateTime)
    gpush_calendar_list_last_ping = Column(DateTime)
    gpush_calendar_list_expiration = Column(DateTime)

    @property
    def provider(self):
        return PROVIDER

    @property
    def category_type(self):
        return 'label'

    @property
    def thread_cls(self):
        from inbox.models.backends.imap import ImapThread
        return ImapThread

    @property
    def actionlog_cls(self):
        from inbox.models.action_log import ActionLog
        return ActionLog

    def new_token(self, scope, client_ids=None):
        """
        Retrieves a new access token w/ access to the given scope.
        Returns a GToken namedtuple.

        If this comes across any invalid refresh_tokens, it'll set the
        auth_credentials' is_valid flag to False.

        If no valid auth tokens are available, throws an OAuthError.

        If client_ids is given, only looks at auth credentials with a client
        id in client_ids.

        """
        non_oauth_error = None

        possible_credentials = [
            auth_creds for auth_creds in self.valid_auth_credentials
            if scope in auth_creds.scopes and (
                client_ids is None or
                auth_creds.client_id in client_ids
            )
        ]

        # If more than one set of credentials is present, we don't want to
        # just use the same one each time.
        shuffle(possible_credentials)

        for auth_creds in possible_credentials:
            try:
                token, expires_in = self.auth_handler.new_token(
                    auth_creds.refresh_token,
                    auth_creds.client_id,
                    auth_creds.client_secret)

                expires_in -= 10
                expiration = (datetime.utcnow() +
                              timedelta(seconds=expires_in))

                return GToken(
                    token, expiration, auth_creds.scopes,
                    auth_creds.client_id, auth_creds.id)

            except OAuthError as e:
                log.error('Error validating',
                          account_id=self.id,
                          auth_creds_id=auth_creds.id,
                          logstash_tag='mark_invalid')
                auth_creds.is_valid = False

            except Exception as e:
                log.error(
                    'Error while getting access token: {}'.format(e),
                    account_id=self.id,
                    auth_creds_id=auth_creds.id,
                    exc_info=True)
                non_oauth_error = e

        if non_oauth_error:
            # Some auth credential might still be valid!
            raise non_oauth_error
        else:
            raise OAuthError("No valid tokens")

    def verify_all_credentials(self):
        for auth_creds in self.valid_auth_credentials:
            if not self.verify_credentials(auth_creds):
                auth_creds.is_valid = False

        valid_scopes = set()
        for auth_creds in self.valid_auth_credentials:
            valid_scopes = valid_scopes.union(set(auth_creds.scopes))

        if GOOGLE_CALENDAR_SCOPE not in valid_scopes:
            self.sync_events = False
        if GOOGLE_CONTACTS_SCOPE not in valid_scopes:
            self.sync_contacts = False
        if GOOGLE_EMAIL_SCOPE not in valid_scopes:
            self.mark_invalid()

    def verify_credentials(self, auth_creds):
        try:
            self.auth_handler.new_token(
                auth_creds.refresh_token,
                auth_creds.client_id,
                auth_creds.client_secret)
            # Valid access token might have changed? This might not
            # be necessary.
            g_token_manager.clear_cache(self)
            return True
        except OAuthError:
            return False

    @property
    def valid_auth_credentials(self):
        return [creds for creds in self.auth_credentials if creds.is_valid]

    def verify(self):
        token = g_token_manager.get_token(self, GOOGLE_EMAIL_SCOPE,
                                          force_refresh=True)
        return self.auth_handler.validate_token(token)

    def new_calendar_list_watch(self, expiration):
        # Google gives us back expiration timestamps in milliseconds
        expiration = datetime.fromtimestamp(int(expiration) / 1000.)
        self.gpush_calendar_list_expiration = expiration

    def handle_gpush_notification(self):
        self.gpush_calendar_list_last_ping = datetime.utcnow()

    def should_update_calendars(self, max_time_between_syncs):
        """
        max_time_between_syncs: a timedelta object. The maximum amount of
        time we should wait until we sync, even if we haven't received
        any push notifications

        """
        return (
            # Never synced
            self.last_calendar_list_sync is None or
            # Too much time has passed to not sync
            (datetime.utcnow() >
                self.last_calendar_list_sync + max_time_between_syncs) or
            # Push notifications channel is stale
            self.needs_new_calendar_list_watch() or
            # Our info is stale, according to google's push notifications
            (
                self.gpush_calendar_list_last_ping is not None and
                (self.last_calendar_list_sync <
                    self.gpush_calendar_list_last_ping)
            )
        )

    def needs_new_calendar_list_watch(self):
        return (self.gpush_calendar_list_expiration is None or
                self.gpush_calendar_list_expiration < datetime.utcnow())


class GmailAuthCredentials(MailSyncBase, UpdatedAtMixin, DeletedAtMixin):
    """
    Associate a Gmail Account with a refresh token using a
    one-to-many relationship. Refresh token ids are actually
    ids of objects in the 'secrets' table.

    A GmailAccount has many GmailAuthCredentials.
    A GmailAuthCredentials entry has a single secret.

    There should be only one GmailAuthCredentials for each
    (gmailaccount, client_id, client_secret) triple.

    If g is a gmail account, you can get all of its refresh tokens w/
    [auth_creds.refresh_token for auth_creds in g.auth_credentials]

    """
    gmailaccount_id = Column(BigInteger,
                             ForeignKey(GmailAccount.id, ondelete='CASCADE'),
                             nullable=False)
    refresh_token_id = Column(BigInteger,
                              ForeignKey(Secret.id, ondelete='CASCADE'),
                              nullable=False)

    _scopes = Column('scopes', String(512), nullable=False)
    g_id_token = Column(String(1024), nullable=False)
    client_id = Column(String(256), nullable=False)
    client_secret = Column(String(256), nullable=False)
    is_valid = Column(Boolean, default=True, nullable=False)

    gmailaccount = relationship(
        GmailAccount,
        backref=backref('auth_credentials', cascade='all, delete-orphan',
                        lazy='joined'),
        lazy='joined',
        join_depth=2
    )

    refresh_token_secret = relationship(
        Secret,
        cascade='all, delete-orphan',
        single_parent=True,
        lazy='joined',
        backref=backref('gmail_auth_credentials')
    )

    @hybrid_property
    def scopes(self):
        return self._scopes.split(' ')

    @scopes.setter
    def scopes(self, value):
        # Can assign a space-separated string or a list of urls
        if isinstance(value, basestring):
            self._scopes = value
        else:
            self._scopes = ' '.join(value)

    @property
    def refresh_token(self):
        if self.refresh_token_secret:
            return self.refresh_token_secret.secret
        return None

    @refresh_token.setter
    def refresh_token(self, value):
        # Must be a valid UTF-8 byte sequence without NULL bytes.
        if isinstance(value, unicode):
            value = value.encode('utf-8')

        try:
            unicode(value, 'utf-8')
        except UnicodeDecodeError:
            raise ValueError('Invalid refresh_token')

        if b'\x00' in value:
            raise ValueError('Invalid refresh_token')

        if not self.refresh_token_secret:
            self.refresh_token_secret = Secret()

        self.refresh_token_secret.secret = value
        self.refresh_token_secret.type = 'token'
