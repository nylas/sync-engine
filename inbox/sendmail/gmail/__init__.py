from inbox.sendmail.gmail.gmail import GmailSMTPClient
from inbox.sendmail.gmail.drafts import create_and_save_draft

__all__ = ['GmailSMTPClient', 'create_and_save_draft']

PROVIDER = 'Gmail'
SENDMAIL_CLS = 'GmailSMTPClient'
