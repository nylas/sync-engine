from datetime import datetime

from inbox.util.encoding import base36decode
from inbox.log import get_logger
from inbox.crispin import RawMessage
from inbox.mailsync.backends.base import (create_db_objects,
                                                 commit_uids)
from inbox.mailsync.backends.gmail import create_gmail_message
from inbox.sendmail.base import all_recipients, generate_attachments
from inbox.sendmail.message import create_email, SenderInfo


def create_and_save_draft(db_session, account, to_addr=None, subject=None,
                          body=None, block_public_ids=None, cc_addr=None,
                          bcc_addr=None, replyto_thread_id=None,
                          parent_draft_id=None):
    """
    Create a new draft object and commit it to the database.

    Notes
    -----
    This is a provider dependant function.

    """
    log = get_logger(account.id, purpose='drafts')

    sender_info = SenderInfo(account.full_name, account.email_address)
    recipients = all_recipients(to_addr, cc_addr, bcc_addr)
    attachments = generate_attachments(block_public_ids)

    mimemsg = create_email(sender_info, None, recipients, subject, body,
                           attachments)

    msg_body = mimemsg.to_string()

    # The generated `X-INBOX-ID` UUID of the message is too big to serve as the
    # msg_uid for the corresponding ImapUid. The msg_uid is a SQL BigInteger
    # (20 bits), so we truncate the `X-INBOX-ID` to that size. Note that
    # this still provides a large enough ID space to make collisions rare.
    x_inbox_id = mimemsg.headers.get('X-INBOX-ID')  # base-36 encoded string
    uid = base36decode(x_inbox_id) & (1 << 20) - 1

    date = datetime.utcnow()
    flags = [u'\\Draft']

    msg = RawMessage(uid=uid, internaldate=date,
                     flags=flags, body=msg_body, g_thrid=None,
                     g_msgid=None, g_labels=set(), created=True)

    # TODO(emfree): this breaks the 'folders just mirror the backend'
    # assumption we want to be able to make.
    new_uids = create_db_objects(account.id, db_session, log,
                                 account.drafts_folder.name, [msg],
                                 create_gmail_message)
    if new_uids:
        assert len(new_uids) == 1
        new_uid = new_uids[0]

        new_uid.created_date = date

        # Set SpoolMessage's special draft attributes
        new_uid.message.state = 'draft'
        new_uid.message.parent_draft_id = parent_draft_id
        new_uid.message.replyto_thread_id = replyto_thread_id

        commit_uids(db_session, log, new_uids)

        return new_uid.message

