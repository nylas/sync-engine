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
# Allow out-of-tree action submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

from inbox.actions.backends import module_registry

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.models import Account, Message
from inbox.models.session import session_scope
from inbox.models.action_log import schedule_action
from inbox.sendmail.base import (generate_attachments, get_sendmail_client,
                                 SendMailException)
from inbox.sendmail.message import create_email, Recipients
from inbox.log import get_logger


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
    account = db_session.query(Account).get(account_id)
    set_remote_unread = module_registry[account.provider]. \
        set_remote_unread
    set_remote_unread(account, thread_id, True, db_session)


def mark_read(account_id, thread_id, db_session):
    account = db_session.query(Account).get(account_id)
    set_remote_unread = module_registry[account.provider]. \
        set_remote_unread
    set_remote_unread(account, thread_id, False, db_session)


def mark_spam(account_id, thread_id, db_session):
    raise NotImplementedError


def unmark_spam(account_id, thread_id, db_session):
    raise NotImplementedError


def mark_trash(account_id, thread_id, db_session):
    raise NotImplementedError


def unmark_trash(account_id, thread_id, db_session):
    raise NotImplementedError


def save_draft(account_id, message_id, db_session):
    """ Sync a new/updated draft back to the remote backend. """
    account = db_session.query(Account).get(account_id)
    message = db_session.query(Message).get(message_id)
    assert message.is_draft

    recipients = Recipients(message.to_addr, message.cc_addr,
                            message.bcc_addr)
    attachments = generate_attachments(message.attachments)
    mimemsg = create_email(account.sender_name, account.email_address,
                           message.inbox_uid, recipients, message.subject,
                           message.sanitized_body, attachments)

    remote_save_draft = module_registry[account.provider].remote_save_draft
    remote_save_draft(account, account.drafts_folder.name,
                      mimemsg.to_string(), message.created_at)


def delete_draft(account_id, draft_id, db_session, args):
    """ Delete a draft from the remote backend. """
    inbox_uid = args.get('inbox_uid')

    with session_scope(ignore_soft_deletes=False) as db_session:
        account = db_session.query(Account).get(account_id)

        # Non-Inbox created draft, therefore standard delete
        if inbox_uid is None:
            draft = db_session.query(Message).get(draft_id)
            remote_delete = \
                module_registry[account.provider].remote_delete
            remote_delete(account, account.drafts_folder.name,
                          draft.thread_id, db_session)
        # Inbox created draft, therefore use X-INBOX header
        else:
            remote_delete_draft = \
                module_registry[account.provider].remote_delete_draft
            remote_delete_draft(account, account.drafts_folder.name,
                                inbox_uid, db_session)


def send_directly(account_id, draft_id, db_session):
    """
    Send a just-created draft (as opposed to one that was previously created
    and synced to the backend.

    """
    _send(account_id, draft_id, db_session)


def send_draft(account_id, draft_id, db_session):
    """Send a previously created draft."""
    _send(account_id, draft_id, db_session)
    draft = db_session.query(Message).get(draft_id)
    # Schedule the deletion separately (we don't want to resend if sending
    # succeeds but deletion fails!)
    schedule_action('delete_draft', draft, draft.namespace.id, db_session,
                    inbox_uid=draft.inbox_uid)


def _send(account_id, draft_id, db_session):
    """Send the draft with id = `draft_id`."""
    account = db_session.query(Account).get(account_id)

    log = get_logger()
    sendmail_client = get_sendmail_client(account)
    try:
        draft = db_session.query(Message).filter(
            Message.id == draft_id).one()

    except NoResultFound:
        log.info('NoResultFound for draft_id {0}'.format(draft_id))
        raise SendMailException('No draft with id {0}'.format(draft_id))

    except MultipleResultsFound:
        log.info('MultipleResultsFound for draft_id {0}'.format(draft_id))
        raise SendMailException('Multiple drafts with id {0}'.format(
            draft_id))

    if not draft.is_draft or draft.is_sent:
        return

    recipients = Recipients(draft.to_addr, draft.cc_addr, draft.bcc_addr)
    if not draft.is_reply:
        sendmail_client.send_new(db_session, draft, recipients)
    else:
        sendmail_client.send_reply(db_session, draft, recipients)

    # Update message
    draft.is_sent = True
    draft.is_draft = False
    draft.state = 'sent'

    # Update thread
    sent_tag = account.namespace.tags['sent']
    draft_tag = account.namespace.tags['drafts']
    draft.thread.apply_tag(sent_tag)
    # Remove the drafts tag from the thread if there are no more drafts.
    if not draft.thread.drafts:
        draft.thread.remove_tag(draft_tag)

    return draft
