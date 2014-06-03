from inbox.server.sendmail.gmail.gmail import GmailSMTPClient
from inbox.server.sendmail.gmail.drafts import (create_database_message,
                                                get_sendmail_client)

# delete_draft, get_draft, get_all_drafts are provider agnostic
__all__ = ['GmailSMTPClient', 'get_sendmail_client', 'create_database_message']

PROVIDER = 'Gmail'
SENDMAIL_CLS = 'GmailSMTPClient'
