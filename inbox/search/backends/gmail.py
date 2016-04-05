import requests
from sqlalchemy import desc
from inbox.basicauth import OAuthError
from inbox.search.base import SearchBackendException
from inbox.auth.oauth import OAuthRequestsWrapper
from inbox.models import Message, Thread, Account
from inbox.models.backends.gmail import g_token_manager
from nylas.logging import get_logger
from inbox.api.kellogs import APIEncoder
from inbox.models.session import session_scope

log = get_logger()

PROVIDER = 'gmail'
SEARCH_CLS = 'GmailSearchClient'


class GmailSearchClient(object):

    def __init__(self, account):
        self.account_id = int(account.id)
        try:
            with session_scope(self.account_id) as db_session:
                self.account = db_session.query(Account).get(self.account_id)
                self.auth_token = g_token_manager.get_token_for_email(self.account)
                db_session.expunge_all()
        except OAuthError:
            raise SearchBackendException(
                "This search can't be performed because the account's "
                "credentials are out of date. Please reauthenticate and try "
                "again.", 403)

    def search_messages(self, db_session, search_query, offset=0, limit=40):
        g_msgids = self._search(search_query, limit=limit)
        if not g_msgids:
            return []
        query = db_session.query(Message). \
            filter(Message.namespace_id == self.account.namespace.id,
                   Message.g_msgid.in_(g_msgids)). \
            order_by(desc(Message.received_date))

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    # We're only issuing a single request to the Gmail API so there's
    # no need to stream it.
    def stream_messages(self, search_query):
        def g():
            encoder = APIEncoder()

            with session_scope(self.account_id) as db_session:
                yield encoder.cereal(self.search_messages(db_session, search_query)) + '\n'

        return g

    def search_threads(self, db_session, search_query, offset=0, limit=40):
        g_msgids = self._search(search_query, limit=limit)
        if not g_msgids:
            return []
        query = db_session.query(Thread). \
            join(Message). \
            filter(Thread.namespace_id == self.account.namespace.id,
                   Message.namespace_id == self.account.namespace.id,
                   Message.g_msgid.in_(g_msgids)). \
            order_by(desc(Message.received_date))

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    def stream_threads(self, search_query):
        def g():
            encoder = APIEncoder()

            with session_scope(self.account_id) as db_session:
                yield encoder.cereal(self.search_threads(db_session, search_query)) + '\n'

        return g

    def _search(self, search_query, limit):
        ret = requests.get(
            u'https://www.googleapis.com/gmail/v1/users/me/messages',
            params={'q': search_query,
                    'maxResults': limit},
            auth=OAuthRequestsWrapper(self.auth_token))
        log.info('Gmail API search request completed',
                 elapsed=ret.elapsed.total_seconds())
        if ret.status_code != 200:
            log.critical('HTTP error making search request',
                         account_id=self.account.id,
                         url=ret.url,
                         response=ret.content)
            raise SearchBackendException(
                "Error issuing search request", 503, server_error=ret.content)
        data = ret.json()
        if 'messages' not in data:
            return []
        # Note that the Gmail API returns g_msgids in hex format. So for
        # example the IMAP X-GM-MSGID 1438297078380071706 corresponds to
        # 13f5db9286538b1a in the API response we have here.
        return [int(m['id'], 16) for m in data['messages']]
