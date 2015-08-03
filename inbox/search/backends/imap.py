from inbox.log import get_logger
from inbox.crispin import CrispinClient
from inbox.providers import provider_info
from inbox.basicauth import NotSupportedError
from inbox.models import Message, Folder, Account
from inbox.models.backends.imap import ImapUid
from inbox.mailsync.backends.imap.generic import uidvalidity_cb

import re
from imaplib import IMAP4

PROVIDER = 'imap'


def format_key(match):
    return "{} ".format(match.group(0).strip()[:-1].upper())


class IMAPSearchClient(object):
    def __init__(self, account):
        self.account_id = account.id
        self.log = get_logger().new(account_id=account.id,
                                    component='search')

    def search_messages(self, db_session, search_query):
        account = db_session.query(Account).get(self.account_id)
        conn = account.auth_handler.connect_account(account)
        try:
            acct_provider_info = provider_info(account.provider)
        except NotSupportedError:
            self.log.warn('Account provider not supported',
                          provider=account.provider)
            raise

        crispin_client = CrispinClient(self.account_id,
                                        acct_provider_info,
                                        account.email_address,
                                        conn,
                                        readonly=True)
        self.log.info('Searching account',
                      account_id=self.account_id,
                      query=search_query)
        if ':' not in search_query:
            try:
                query = search_query.encode('ascii')
                criteria = 'TEXT {}'.format(query)
            except UnicodeEncodeError:
                criteria = u'TEXT {}'.format(search_query)
        else:
            criteria = re.sub('(\w+:[ ]?)', format_key, search_query)

        all_messages = set()
        folders = db_session.query(Folder).filter(
            Folder.account_id == self.account_id).all()

        for folder in folders:
            all_messages.update(self.search_folder(db_session,
                                                   crispin_client,
                                                   folder, criteria))

        crispin_client.logout()

        return sorted(all_messages, key=lambda msg: msg.received_date,
                      reverse=True)

    def search_threads(self, db_session, search_query):
        messages = self.search_messages(db_session, search_query)
        all_threads = {m.thread for m in messages}

        self.log.debug('Search found threads for folder',
                       threads=len(all_threads))

        return sorted(all_threads, key=lambda thread: thread.recentdate,
                      reverse=True)

    def search_folder(self, db_session, crispin_client, folder,
                        criteria):
        account = db_session.query(Account).get(self.account_id)
        crispin_client.select_folder(folder.name, uidvalidity_cb)
        try:
            if isinstance(criteria, unicode):
                matching_uids = crispin_client.conn.search(criteria=criteria,
                                                           charset="UTF-8")
            else:
                matching_uids = crispin_client.conn.search(criteria=criteria)
        except IMAP4.error as e:
            self.log.warn('Search error', error=e)
            raise

        all_messages = db_session.query(Message) \
            .join(ImapUid) \
            .join(Folder) \
            .filter(Folder.id == folder.id,
                    ImapUid.account_id == account.id,
                    ImapUid.msg_uid.in_(matching_uids)).all()

        self.log.debug('Search found message for folder',
                        folder_name=folder.name,
                        matching_uids=len(matching_uids),
                        messages_synced=len(all_messages))

        return all_messages
