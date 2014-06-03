from inbox.server.mailsync.backends.gmail import create_gmail_message
from inbox.server.sendmail.gmail.gmail import GmailSMTPClient


create_database_message = create_gmail_message


# TODO(emfree) move elsewhere
def get_sendmail_client(account_id, namespace):
    return GmailSMTPClient(account_id, namespace)
