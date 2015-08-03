from inbox.crispin import GmailCrispinClient
from inbox.models import Message, Folder, Account
from inbox.providers import provider_info
from inbox.models.backends.imap import ImapUid
from inbox.search.backends.imap import IMAPSearchClient
from inbox.mailsync.backends.imap.generic import uidvalidity_cb

PROVIDER = 'gmail'
SEARCH_CLS = 'GmailSearchClient'


class GmailSearchClient(IMAPSearchClient):
    def search_messages(self, db_session, search_query):
        account = db_session.query(Account).get(self.account_id)
        conn = account.auth_handler.connect_account(account)
        crispin_client = GmailCrispinClient(self.account_id,
                                            provider_info('gmail'),
                                            account.email_address,
                                            conn,
                                            readonly=True)
        self.log.info('Searching account',
                      account_id=self.account_id,
                      query=search_query)

        all_messages = set()
        folders = db_session.query(Folder).filter(
            Folder.account_id == self.account_id).all()

        for folder in folders:
            all_messages.update(self.search_folder(db_session,
                                                   crispin_client,
                                                   folder, search_query))

        crispin_client.logout()

        return sorted(all_messages, key=lambda msg: msg.received_date,
                      reverse=True)

    def search_folder(self, db_session, crispin_client, folder, search_query):
        crispin_client.select_folder(folder.name, uidvalidity_cb)
        try:
            try:
                query = search_query.encode('ascii')
                matching_uids = crispin_client.conn.gmail_search(query)
            except UnicodeEncodeError:
                matching_uids = \
                    crispin_client.conn.gmail_search(search_query,
                                                     charset="UTF-8")
        except Exception as e:
            self.log.debug('Search error', error=e)
            raise

        all_messages = db_session.query(Message) \
            .join(ImapUid) \
            .join(Folder) \
            .filter(Folder.id == folder.id,
                    ImapUid.account_id == self.account_id,
                    ImapUid.msg_uid.in_(matching_uids)).all()

        self.log.debug('Search found message for folder',
                        folder_name=folder.name,
                        matching_uids=len(matching_uids),
                        messages_synced=len(all_messages))

        return all_messages
