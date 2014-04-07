from inbox.server.models import new_db_session
from inbox.server.sendmail.postel import SMTPClient
from inbox.server.sendmail.message import (create_gmail_email,
                                           save_gmail_email,
                                           SenderInfo)

PROVIDER = 'Gmail'
SENDMAIL_CLS = 'GmailSMTPClient'


class GmailSMTPClient(SMTPClient):
    def send_mail(self, recipients, subject, body, attachments=None):
        db_session = new_db_session()

        sender_info = SenderInfo(name=self.full_name, email=self.email_address)
        recipients, mimemsg = create_gmail_email(sender_info, recipients,
                                                 subject, body, attachments)

        # Save it to the local datastore
        new_uid = save_gmail_email(self.account_id, db_session, self.log,
                                   mimemsg.uid, mimemsg.msg)

        # Send it
        result = self._send(recipients, mimemsg.msg)

        new_uid.message.is_sent = result
        db_session.commit()

        return result
