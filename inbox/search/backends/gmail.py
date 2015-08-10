from inbox.crispin import GmailCrispinClient
from inbox.models import Account, Folder
from inbox.providers import provider_info
from inbox.search.backends.imap import IMAPSearchClient
from inbox.mailsync.backends.imap.generic import uidvalidity_cb

PROVIDER = 'gmail'
SEARCH_CLS = 'GmailSearchClient'


class GmailSearchClient(IMAPSearchClient):
    def _open_crispin_connection(self, db_session):
        account = db_session.query(Account).get(self.account_id)
        conn = account.auth_handler.connect_account(account)
        self.crispin_client = GmailCrispinClient(self.account_id,
                                                 provider_info('gmail'),
                                                 account.email_address,
                                                 conn,
                                                 readonly=True)

    def _search_folder(self, db_session, folder, search_query):
        self.crispin_client.select_folder(folder.name, uidvalidity_cb)
        try:
            try:
                query = search_query.encode('ascii')
                matching_uids = self.crispin_client.conn.gmail_search(query)
            except UnicodeEncodeError:
                matching_uids = \
                    self.crispin_client.conn.gmail_search(search_query,
                                                          charset="UTF-8")
        except Exception as e:
            self.log.debug('Search error', error=e)
            raise

        self.log.debug('Search found message for folder',
                        folder_name=folder.name,
                        matching_uids=len(matching_uids))

        return matching_uids

    def _search(self, db_session, search_query):
        self._open_crispin_connection(db_session)
        folders = db_session.query(Folder).filter(
            Folder.account_id == self.account_id).all()

        imap_uids = set()

        for folder in folders:
            imap_uids.update(self._search_folder(db_session,
                                                  folder, search_query))
        self._close_crispin_connection()
        return imap_uids
