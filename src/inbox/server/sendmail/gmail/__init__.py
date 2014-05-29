from inbox.server.sendmail.gmail.gmail import GmailSMTPClient
from inbox.server.sendmail.gmail.drafts import (new, reply, update, delete,
                                                send, get, get_all)
__all__ = ['GmailSMTPClient', 'new', 'reply', 'update', 'delete', 'send',
           'get', 'get_all']

PROVIDER = 'Gmail'
SENDMAIL_CLS = 'GmailSMTPClient'
