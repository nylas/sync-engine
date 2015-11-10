from nylas.logging import get_logger
from inbox.crispin import CrispinClient
from inbox.providers import provider_info
from inbox.basicauth import NotSupportedError
from inbox.models import Message, Folder, Account, Thread
from inbox.models.backends.imap import ImapUid
from inbox.mailsync.backends.imap.generic import uidvalidity_cb

import re
from sqlalchemy import desc
from imaplib import IMAP4

PROVIDER = 'imap'


def format_key(match):
    return "{} ".format(match.group(0).strip()[:-1].upper())


class IMAPSearchClient(object):

    def __init__(self, account):
        self.account_id = account.id
        self.log = get_logger().new(account_id=account.id,
                                    component='search')

    def _open_crispin_connection(self, db_session):
        account = db_session.query(Account).get(self.account_id)
        conn = account.auth_handler.connect_account(account)
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
        if ':' not in search_query:
            try:
                query = search_query.encode('ascii')
                criteria = 'TEXT {}'.format(query)
            except UnicodeEncodeError:
                criteria = u'TEXT {}'.format(search_query)
        else:
            criteria = re.sub('(\w+:[ ]?)', format_key, search_query)

        folders = db_session.query(Folder).filter(
            Folder.account_id == self.account_id).all()

        imap_uids = set()

        for folder in folders:
            imap_uids.update(self._search_folder(db_session,
                                                 folder, criteria))
        self._close_crispin_connection()
        return imap_uids

    def _search_folder(self, db_session, folder, criteria):
        self.crispin_client.select_folder(folder.name, uidvalidity_cb)
        try:
            if isinstance(criteria, unicode):
                matching_uids = self.crispin_client.conn. \
                    search(criteria=criteria, charset="UTF-8")
            else:
                matching_uids = self.crispin_client.conn. \
                    search(criteria=criteria)
        except IMAP4.error as e:
            self.log.warn('Search error', error=e)
            raise

        self.log.debug('Search found message for folder',
                       folder_name=folder.name,
                       matching_uids=len(matching_uids))

        return matching_uids
