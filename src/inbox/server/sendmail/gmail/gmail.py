from inbox.server.models.tables.imap import ImapAccount, ImapUid
from inbox.server.actions.gmail import local_move
from inbox.server.sendmail.postel import SMTPClient, SendError
from inbox.server.sendmail.message import SenderInfo
from inbox.server.sendmail.gmail.message import (create_gmail_email,
                                                 create_gmail_reply)


class GmailSMTPClient(SMTPClient):
    """ SMTPClient for Gmail. """
    def _send_mail(self, db_session, imapuid, smtpmsg):
        """
        Send the email message, update the message stored in the local data
        store.

        """
        account = db_session.query(ImapAccount).get(self.account_id)
        draftuid = db_session.query(ImapUid).get(imapuid.id)

        draftuid.message.state = 'sending'

        # Send it using SMTP:
        try:
            result = self._send(smtpmsg.recipients, smtpmsg.msg)
        except SendError as e:
            self.log.error(str(e))
            raise

        # Update saved message in local data store:
        # Update ImapUid
        draftuid.folder = account.sent_folder
        draftuid.is_draft = False

        # Update SpoolMessage
        draftuid.message.is_sent = result
        draftuid.message.is_draft = False
        draftuid.message.state = 'sent'

        draftuid.message.in_reply_to = smtpmsg.in_reply_to
        draftuid.message.references = smtpmsg.references
        draftuid.message.subject = smtpmsg.subject

        # Move thread locally
        local_move(db_session, account, draftuid.message.thread_id,
                   account.drafts_folder.name, account.sent_folder.name)

        db_session.commit()

        return result

    def send_new(self, db_session, imapuid, recipients, subject, body,
                 attachments=None):
        """
        Send a previously created + saved draft email from this user account.

        """
        sender_info = SenderInfo(name=self.full_name, email=self.email_address)
        smtpmsg = create_gmail_email(sender_info, recipients, subject, body,
                                     attachments)
        return self._send_mail(db_session, imapuid, smtpmsg)

    def send_reply(self, db_session, imapuid, replyto, recipients, subject,
                   body, attachments=None):
        """
        Send a previously created + saved draft email reply from this user
        account.

        """
        sender_info = SenderInfo(name=self.full_name, email=self.email_address)
        smtpmsg = create_gmail_reply(sender_info, replyto, recipients, subject,
                                     body, attachments)

        return self._send_mail(db_session, imapuid, smtpmsg)
