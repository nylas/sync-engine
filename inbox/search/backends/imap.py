from nylas.logging import get_logger
from inbox.crispin import CrispinClient
from inbox.providers import provider_info
from inbox.basicauth import NotSupportedError
from inbox.models import Message, Folder, Account, Thread
from inbox.models.backends.imap import ImapUid
from inbox.mailsync.backends.imap.generic import uidvalidity_cb
from inbox.basicauth import ValidationError
from inbox.search.base import SearchBackendException

from sqlalchemy import desc
from imaplib import IMAP4

PROVIDER = 'imap'


class IMAPSearchClient(object):

    def __init__(self, account):
        self.account_id = account.id
        self.log = get_logger().new(account_id=account.id,
                                    component='search')

    def _open_crispin_connection(self, db_session):
        account = db_session.query(Account).get(self.account_id)
        try:
            conn = account.auth_handler.connect_account(account)
        except ValidationError:
            raise SearchBackendException(
                "This search can't be performed because the account's "
                "credentials are out of date. Please reauthenticate and try "
                "again.", 403)

        try:
            acct_provider_info = provider_info(account.provider)
        except NotSupportedError:
            self.log.warn('Account provider not supported',
                          provider=account.provider)
            raise

        self.crispin_client = CrispinClient(self.account_id,
                                            acct_provider_info,
                                            account.email_address,
                                            conn,
                                            readonly=True)

    def _close_crispin_connection(self):
        self.crispin_client.logout()

    def search_messages(self, db_session, search_query, offset=0, limit=40):
        self.log.info('Searching account for messages',
                      account_id=self.account_id,
                      query=search_query,
                      offset=offset,
                      limit=limit)

        imap_uids = self._search(db_session, search_query)
        query = db_session.query(Message) \
            .join(ImapUid) \
            .filter(ImapUid.account_id == self.account_id,
                    ImapUid.msg_uid.in_(imap_uids))\
            .order_by(desc(Message.received_date))\

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    def search_threads(self, db_session, search_query, offset=0, limit=40):
        self.log.info('Searching account for threads',
                      account_id=self.account_id,
                      query=search_query,
                      offset=offset,
                      limit=limit)

        imap_uids = self._search(db_session, search_query)
        query = db_session.query(Thread) \
            .join(Message) \
            .join(ImapUid) \
            .filter(ImapUid.account_id == self.account_id,
                    ImapUid.msg_uid.in_(imap_uids),
                    Thread.id == Message.thread_id)\
            .order_by(desc(Message.received_date))

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    def _search(self, db_session, search_query):
        self._open_crispin_connection(db_session)

        try:
            criteria = ['TEXT', search_query.encode('ascii')]
            charset = None
        except UnicodeEncodeError:
            criteria = [u'TEXT', search_query]
            charset = 'UTF-8'

        folders = db_session.query(Folder).filter(
            Folder.account_id == self.account_id).all()

        imap_uids = set()
        for folder in folders:
            imap_uids.update(self._search_folder(folder,
                                                 criteria,
                                                 charset))
        self._close_crispin_connection()
        return imap_uids

    def _search_folder(self, folder, criteria, charset):
        self.crispin_client.select_folder(folder.name, uidvalidity_cb)
        try:
            uids = self.crispin_client.conn.search(criteria, charset=charset)
        except IMAP4.error as e:
            self.log.warn('Search error', error=e)
            raise

        self.log.debug('Search found messages for folder',
                       folder_name=folder.name,
                       uids=len(uids))
        return uids
