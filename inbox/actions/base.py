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

from inbox.models import Account, Message
from inbox.sendmail.base import generate_attachments
from inbox.sendmail.message import create_email
from nylas.logging import get_logger
log = get_logger()


def mark_unread(account_id, message_id, db_session, args):
    unread = args['unread']

    account = db_session.query(Account).get(account_id)
    set_remote_unread = module_registry[account.provider]. \
        set_remote_unread
    set_remote_unread(account, message_id, db_session, unread)


def mark_starred(account_id, message_id, db_session, args):
    starred = args['starred']
    account = db_session.query(Account).get(account_id)
    set_remote_starred = module_registry[account.provider]. \
        set_remote_starred
    set_remote_starred(account, message_id, db_session, starred)


def move(account_id, message_id, db_session, args):
    destination = args['destination']
    account = db_session.query(Account).get(account_id)
    remote_move = module_registry[account.provider].remote_move
    remote_move(account, message_id, db_session, destination)


def change_labels(account_id, message_id, db_session, args):
    added_labels = args['added_labels']
    removed_labels = args['removed_labels']
    account = db_session.query(Account).get(account_id)
    assert account.provider == 'gmail'
    remote_change_labels = module_registry[account.provider]. \
        remote_change_labels
    remote_change_labels(account, message_id, db_session, removed_labels,
                         added_labels)


def create_folder(account_id, category_id, db_session):
    account = db_session.query(Account).get(account_id)
    remote_create = module_registry[account.provider].remote_create_folder
    remote_create(account, category_id, db_session)


def create_label(account_id, category_id, db_session):
    account = db_session.query(Account).get(account_id)
    assert account.provider == 'gmail'
    remote_create = module_registry[account.provider].remote_create_label
    remote_create(account, category_id, db_session)


def update_folder(account_id, category_id, db_session, args):
    old_name = args['old_name']
    account = db_session.query(Account).get(account_id)
    remote_update = module_registry[account.provider].remote_update_folder
    remote_update(account, category_id, db_session, old_name)


def update_label(account_id, category_id, db_session, args):
    old_name = args['old_name']
    account = db_session.query(Account).get(account_id)
    assert account.provider == 'gmail'
    remote_update = module_registry[account.provider].remote_update_label
    remote_update(account, category_id, db_session, old_name)


def _create_email(account, message):
    blocks = [p.block for p in message.attachments]
    attachments = generate_attachments(blocks)
    from_name, from_email = message.from_addr[0]
    msg = create_email(from_name=from_name,
                       from_email=from_email,
                       reply_to=message.reply_to,
                       inbox_uid=message.inbox_uid,
                       to_addr=message.to_addr,
                       cc_addr=message.cc_addr,
                       bcc_addr=message.bcc_addr,
                       subject=message.subject,
                       html=message.body,
                       in_reply_to=message.in_reply_to,
                       references=message.references,
                       attachments=attachments)
    return msg


def save_draft(account_id, message_id, db_session, args):
    """ Sync a new/updated draft back to the remote backend. """
    account = db_session.query(Account).get(account_id)
    message = db_session.query(Message).get(message_id)
    version = args.get('version')
    if message is None:
        log.info('tried to save nonexistent message as draft',
                 message_id=message_id, account_id=account_id)
        return
    if not message.is_draft:
        log.warning('tried to save non-draft message as draft',
                    message_id=message_id,
                    account_id=account_id)
        return
    if version != message.version:
        log.warning('tried to save outdated version of draft')
        return

    mimemsg = _create_email(account, message)
    remote_save_draft = module_registry[account.provider].remote_save_draft
    remote_save_draft(account, mimemsg, db_session, message.created_at)


def delete_draft(account_id, draft_id, db_session, args):
    """
    Delete a draft from the remote backend. `args` should contain an
    `inbox_uid` or a `message_id_header` key. This is used to find the draft on
    "the backend.

    """
    inbox_uid = args.get('inbox_uid')
    message_id_header = args.get('message_id_header')
    assert inbox_uid or message_id_header, 'Need at least one header value'
    account = db_session.query(Account).get(account_id)
    remote_delete_draft = module_registry[account.provider].remote_delete_draft
    remote_delete_draft(account, inbox_uid, message_id_header, db_session)


def save_sent_email(account_id, message_id, db_session):
    """
    Create an email on the remote backend. Only used to work
    around providers who don't save sent messages themselves
    (I'm looking at you, iCloud).

    """
    account = db_session.query(Account).get(account_id)
    message = db_session.query(Message).get(message_id)
    if message is None:
        log.info('tried to create nonexistent message',
                 message_id=message_id, account_id=account_id)
        return

    mimemsg = _create_email(account, message)
    remote_save_sent = module_registry[account.provider].remote_save_sent
    remote_save_sent(account, mimemsg, message.created_at)
