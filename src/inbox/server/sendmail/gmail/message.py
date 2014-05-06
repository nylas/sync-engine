from collections import namedtuple
from datetime import datetime

from flanker.addresslib import address

from inbox.server.crispin import RawMessage
from inbox.server.models.tables.base import Account
from inbox.server.models.tables.imap import ImapThread
from inbox.server.mailsync.backends.base import create_db_objects, commit_uids
from inbox.server.mailsync.backends.imap.account import create_gmail_message
from inbox.server.sendmail.message import (create_email, add_reply_headers,
                                           rfc_transform)

SMTPMessage = namedtuple('SMTPMessage', 'inbox_uid msg recipients thread_id')


def smtp_attrs(msg, thread_id=None):
    """ Generate the SMTP recipients, RFC compliant SMTP message. """
    # SMTP recipients include addresses in To-, Cc- and Bcc-
    all_recipients = u', '.\
        join([m for m in msg.headers.get('To'),
             msg.headers.get('Cc'),
             msg.headers.get('Bcc') if m])

    recipients = [a.full_spec() for a in address.parse_list(all_recipients)]

    # Keep Cc-, but strip Bcc-
    # Gmail actually keeps Bcc- on the bcc- recipients (only!) but
    # for now, we strip for all. Exchange does this too so it's not a big deal.
    msg.remove_headers('Bcc')

    # Create an RFC-2821 compliant SMTP message
    rfcmsg = rfc_transform(msg)

    smtpmsg = SMTPMessage(inbox_uid=msg.headers.get('X-INBOX-ID'),
                          msg=rfcmsg,
                          recipients=recipients,
                          thread_id=thread_id)

    return smtpmsg


def create_gmail_email(sender_info, recipients, subject, body,
                       attachments=None):
    """ Create a Gmail email. """
    mimemsg = create_email(sender_info, recipients, subject, body, attachments)

    return smtp_attrs(mimemsg)


def create_gmail_reply(replyto, sender_info, recipients, subject, body,
                       attachments=None):
    """ Create a Gmail email reply. """
    mimemsg = create_email(sender_info, recipients, subject, body, attachments)

    # Add general reply headers:
    reply = add_reply_headers(replyto, mimemsg)

    # Set the 'Subject' header of the reply, required for Gmail.
    # Gmail requires the same subject as the original (adding Re:/Fwd: is fine
    # though) to group messages in the same conversation,
    # See: https://support.google.com/mail/answer/5900?hl=en
    replystr = 'Re: '
    reply.headers['Subject'] = replystr + replyto.subject

    return smtp_attrs(reply, replyto.thread_id)


def save_gmail_email(account_id, sent_folder, db_session, log, smtpmsg):
    """
    Save the email message to the local data store.

    Notes
    -----
    The message is stored as a SpoolMessage, to be reconciled at a
    future sync.

    """
    # The generated `X-INBOX-ID` UUID of the message is too big to serve as the
    # msg_uid for the corresponding ImapUid. The msg_uid is a SQL BigInteger
    # (20 bits), so we truncate the `X-INBOX-ID` to that size. Note that
    # this still provides a large enough ID space to make collisions rare.
    uid = (int(smtpmsg.inbox_uid, 16)) & (1 << 20) - 1
    date = datetime.utcnow()

    # Create a new SpoolMessage:
    msg = RawMessage(uid=uid, internaldate=date, flags=set(),
                     body=smtpmsg.msg, g_thrid=smtpmsg.thread_id,
                     g_msgid=None, g_labels=set(), created=True)
    new_uids = create_db_objects(account_id, db_session, log, sent_folder,
                                 [msg], create_gmail_message)

    assert len(new_uids) == 1
    new_uids[0].created_date = date

    commit_uids(db_session, log, new_uids)

    return new_uids[0]
