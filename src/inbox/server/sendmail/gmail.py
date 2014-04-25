from collections import namedtuple

from inbox.server.models import new_db_session, session_scope
from inbox.server.models.tables.imap import ImapThread
from inbox.server.sendmail.postel import SMTPClient
from inbox.server.sendmail.message import SenderInfo, ReplyToMessage
from inbox.server.sendmail.gmailmessage import (create_gmail_email,
                                                create_gmail_reply,
                                                save_gmail_email)

PROVIDER = 'Gmail'
SENDMAIL_CLS = 'GmailSMTPClient'


class GmailSMTPClient(SMTPClient):
    """ SMTPClient for Gmail. """
    def _send_mail(self, smtpmsg):
        with session_scope() as db_session:
            # Save the email message to the local datastore
            new_uid = save_gmail_email(self.account_id, db_session, self.log,
                                       smtpmsg)

            # Send it using SMTP
            result = self._send(smtpmsg.recipients, smtpmsg.msg)

            new_uid.message.is_sent = result
            db_session.commit()

            return result

    def send_new(self, recipients, subject, body, attachments=None):
        sender_info = SenderInfo(name=self.full_name, email=self.email_address)
        smtpmsg = create_gmail_email(sender_info, recipients, subject, body,
                                     attachments)

        return self._send_mail(smtpmsg)

    def send_reply(self, thread_id, recipients, subject, body,
                   attachments=None):
        with session_scope() as db_session:
            thread = db_session.query(ImapThread).filter(\
                ImapThread.id == thread_id,
                ImapThread.namespace_id == self.namespace.id).one()
            g_thrid = thread.g_thrid
            thread_subject = thread.subject
            # The first message is the latest message we have for this thread
            message_id = thread.messages[0].message_id_header
            # The references are JWZ compliant
            references = thread.messages[0].references
            body = thread.messages[0].prettified_body

        replyto = ReplyToMessage(thread_id=g_thrid, subject=thread_subject,
                                 message_id=message_id, references=references,
                                 body=body)
        sender_info = SenderInfo(name=self.full_name, email=self.email_address)

        smtpmsg = create_gmail_reply(replyto, sender_info, recipients, subject,
                                     body, attachments)
        return self._send_mail(smtpmsg)
