from inbox.models.namespace import db_write_lock
from inbox.models.tables.imap import ImapAccount, ImapUid
from inbox.sendmail.base import generate_attachments, SendError
from inbox.sendmail.postel import SMTPClient
from inbox.sendmail.message import SenderInfo
from inbox.sendmail.gmail.message import (create_gmail_email,
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

        # Update thread
        sent_tag = self.namespace.tags['sent']
        draftuid.message.thread.apply_tag(sent_tag)

        # Remove from drafts folder
        # TODO(emfree) don't put it in the drafts folder in the first place --
        # just apply the drafts tag on creation.
        with db_write_lock(self.namespace.id):
            drafts_folder = account.drafts_folder
            draftuid.message.thread.folders.discard(drafts_folder)

        db_session.commit()

        return draftuid.message

    def send_new(self, db_session, draft, recipients, block_public_ids=None):
        """
        Send a previously created + saved draft email from this user account.

        """
        imapuid = draft.imapuids[0]
        inbox_uid = draft.inbox_uid
        subject = draft.subject
        body = draft.sanitized_body
        attachments = generate_attachments(block_public_ids)
        sender_info = SenderInfo(name=self.full_name, email=self.email_address)

        smtpmsg = create_gmail_email(sender_info, inbox_uid, recipients,
                                     subject, body, attachments)
        return self._send_mail(db_session, imapuid, smtpmsg)

    def send_reply(self, db_session, draft, replyto, recipients,
                   block_public_ids=None):
        """
        Send a previously created + saved draft email reply from this user
        account.

        """
        imapuid = draft.imapuids[0]
        inbox_uid = draft.inbox_uid
        subject = draft.subject
        body = draft.sanitized_body
        attachments = generate_attachments(block_public_ids)
        sender_info = SenderInfo(name=self.full_name, email=self.email_address)

        smtpmsg = create_gmail_reply(sender_info, replyto, inbox_uid,
                                     recipients, subject, body, attachments)

        return self._send_mail(db_session, imapuid, smtpmsg)
