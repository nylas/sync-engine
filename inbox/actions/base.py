""" Code for propagating Inbox datastore changes to account backends.

Syncback actions don't update anything in the local datastore; the Inbox
datastore is updated asynchronously (see namespace.py) and bookkeeping about
the account backend state is updated when the changes show up in the mail sync
engine.

Dealing with write actions separately from read syncing allows us more
flexibility in responsiveness/latency on data propagation, and also makes us
unable to royally mess up a sync and e.g. accidentally delete a bunch of
messages on the account backend because our local datastore is messed up.

This read/write separation also allows us to easily disable syncback for
testing.

The main problem the separation presents is the fact that the read syncing
needs to deal with the fact that the local datastore may have new changes to
it that are not yet reflected in the account backend. In practice, this is
not really a problem because of the limited ways mail messages can change.
(For more details, see individual account backend submodules.)

ACTIONS MUST BE IDEMPOTENT! We are going to have task workers guarantee
at-least-once semantics.
"""
from inbox.actions.backends import module_registry

from inbox.models import Account, Message, Thread, Folder
from inbox.sendmail.base import generate_attachments
from inbox.sendmail.message import create_email
from inbox.log import get_logger
log = get_logger()


def archive(account_id, thread_id, db_session):
    """Sync an archive action back to the backend. """
    account = db_session.query(Account).get(account_id)

    set_remote_archived = module_registry[account.provider]. \
        set_remote_archived
    set_remote_archived(account, thread_id, True, db_session)


def unarchive(account_id, thread_id, db_session):
    account = db_session.query(Account).get(account_id)

    set_remote_archived = module_registry[account.provider]. \
        set_remote_archived
    set_remote_archived(account, thread_id, False, db_session)


def star(account_id, thread_id, db_session):
    account = db_session.query(Account).get(account_id)

    set_remote_starred = module_registry[account.provider]. \
        set_remote_starred
    set_remote_starred(account, thread_id, True, db_session)


def unstar(account_id, thread_id, db_session):
    account = db_session.query(Account).get(account_id)

    set_remote_starred = module_registry[account.provider]. \
        set_remote_starred
    set_remote_starred(account, thread_id, False, db_session)


def mark_unread(account_id, thread_id, db_session):
    thread = db_session.query(Thread).get(thread_id)
    for message in thread.messages:
        message.is_read = False
    account = db_session.query(Account).get(account_id)
    set_remote_unread = module_registry[account.provider]. \
        set_remote_unread
    set_remote_unread(account, thread_id, True, db_session)


def mark_read(account_id, thread_id, db_session):
    thread = db_session.query(Thread).get(thread_id)
    for message in thread.messages:
        message.is_read = True
    account = db_session.query(Account).get(account_id)
    set_remote_unread = module_registry[account.provider]. \
        set_remote_unread
    set_remote_unread(account, thread_id, False, db_session)


def mark_spam(account_id, thread_id, db_session):
    """Sync a mark as spam action back to the backend. """
    account = db_session.query(Account).get(account_id)

    set_remote_spam = module_registry[account.provider]. \
        set_remote_spam
    set_remote_spam(account, thread_id, True, db_session)


def unmark_spam(account_id, thread_id, db_session):
    """Sync an unmark as spam action back to the backend. """
    account = db_session.query(Account).get(account_id)

    set_remote_spam = module_registry[account.provider]. \
        set_remote_spam
    set_remote_spam(account, thread_id, False, db_session)


def mark_trash(account_id, thread_id, db_session):
    """Sync an trash action back to the backend. """
    account = db_session.query(Account).get(account_id)

    set_remote_trash = module_registry[account.provider]. \
        set_remote_trash
    set_remote_trash(account, thread_id, True, db_session)


def unmark_trash(account_id, thread_id, db_session):
    """Sync an trash action back to the backend. """
    account = db_session.query(Account).get(account_id)

    set_remote_trash = module_registry[account.provider]. \
        set_remote_trash
    set_remote_trash(account, thread_id, False, db_session)


def _create_email(account, message):
    blocks = [p.block for p in message.attachments]
    attachments = generate_attachments(blocks)
    msg = create_email(sender_name=account.name,
                       sender_email=account.email_address,
                       inbox_uid=message.inbox_uid,
                       to_addr=message.to_addr,
                       cc_addr=message.cc_addr,
                       bcc_addr=message.bcc_addr,
                       subject=message.subject,
                       html=message.sanitized_body,
                       in_reply_to=message.in_reply_to,
                       references=message.references,
                       attachments=attachments)
    return msg


def save_draft(account_id, message_id, db_session):
    """ Sync a new/updated draft back to the remote backend. """
    account = db_session.query(Account).get(account_id)
    message = db_session.query(Message).get(message_id)
    if message is None:
        log.info('tried to save nonexistent message as draft',
                 message_id=message_id, account_id=account_id)
        return
    if not message.is_draft:
        log.warning('tried to save non-draft message as draft',
                    message_id=message_id,
                    account_id=account_id)
        return

    if account.drafts_folder is None:
        # account has no detected drafts folder - create one.
        drafts_folder = Folder.find_or_create(db_session, account,
                                              'Drafts', 'drafts')
        account.drafts_folder = drafts_folder

    mimemsg = _create_email(account, message)
    remote_save_draft = module_registry[account.provider].remote_save_draft
    remote_save_draft(account, account.drafts_folder.name,
                      mimemsg, db_session, message.created_at)


def delete_draft(account_id, draft_id, db_session, args):
    """ Delete a draft from the remote backend. `args` should contain an
    `inbox_uid` or a `message_id_header` key. This is used to find the draft on
    "the backend."""
    inbox_uid = args.get('inbox_uid')
    message_id_header = args.get('message_id_header')
    assert inbox_uid or message_id_header, 'Need at least one header value'
    account = db_session.query(Account).get(account_id)
    remote_delete_draft = module_registry[account.provider].remote_delete_draft
    remote_delete_draft(account, inbox_uid, message_id_header, db_session)


def save_sent_email(account_id, message_id, db_session):
    """ Create an email on the remote backend. Only used to work
    around providers who don't save sent messages themselves
    (I'm looking at you, iCloud)."""
    account = db_session.query(Account).get(account_id)
    message = db_session.query(Message).get(message_id)
    if message is None:
        log.info('tried to create nonexistent message',
                 message_id=message_id, account_id=account_id)
        return

    create_backend_sent_folder = False
    if account.sent_folder is None:
        # account has no detected drafts folder - create one.
        sent_folder = Folder.find_or_create(db_session, account,
                                            'Sent', 'sent')
        account.sent_folder = sent_folder
        create_backend_sent_folder = True

    mimemsg = _create_email(account, message)
    remote_save_sent = module_registry[account.provider].remote_save_sent
    remote_save_sent(account, account.sent_folder.name,
                     mimemsg, message.created_at,
                     create_backend_sent_folder)
