""" Code for propagating Nylas datastore changes to account backends.

Syncback actions don't update anything in the local datastore; the Nylas
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
from inbox.actions.backends.generic import (set_remote_unread,
                                            set_remote_starred, remote_move,
                                            remote_save_draft,
                                            remote_update_draft,
                                            remote_delete_draft,
                                            remote_save_sent,
                                            remote_create_folder,
                                            remote_update_folder,
                                            remote_delete_folder,
                                            remote_delete_sent)
from inbox.actions.backends.gmail import (remote_change_labels,
                                          remote_create_label,
                                          remote_update_label,
                                          remote_delete_label)

from inbox.models import Message
from inbox.models.session import session_scope
from nylas.logging import get_logger
log = get_logger()


def mark_unread(account_id, message_id, args):
    unread = args['unread']
    set_remote_unread(account_id, message_id, unread)


def mark_starred(account_id, message_id, args):
    starred = args['starred']
    set_remote_starred(account_id, message_id, starred)


def move(account_id, message_id, args):
    destination = args['destination']
    remote_move(account_id, message_id, destination)


def change_labels(account_id, message_id, args):
    added_labels = args['added_labels']
    removed_labels = args['removed_labels']
    remote_change_labels(account_id, message_id, removed_labels,
                         added_labels)


def create_folder(account_id, category_id):
    remote_create_folder(account_id, category_id)


def create_label(account_id, category_id):
    remote_create_label(account_id, category_id)


def delete_label(account_id, category_id):
    remote_delete_label(account_id, category_id)


def update_folder(account_id, category_id, args):
    old_name = args['old_name']
    remote_update_folder(account_id, category_id, old_name)


def delete_folder(account_id, category_id):
    remote_delete_folder(account_id, category_id)


def update_label(account_id, category_id, args):
    old_name = args['old_name']
    remote_update_label(account_id, category_id, old_name)


def save_draft(account_id, message_id, args):
    """ Sync a new draft back to the remote backend. """
    with session_scope(account_id) as db_session:
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

    remote_save_draft(account_id, message_id)


def update_draft(account_id, message_id, args):
    """ Sync an updated draft back to the remote backend. """
    with session_scope(account_id) as db_session:
        message = db_session.query(Message).get(message_id)
        version = args.get('version')
        old_message_id_header = args.get('old_message_id_header')

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

    remote_update_draft(account_id, message_id, old_message_id_header)


def delete_draft(account_id, draft_id, args):
    """
    Delete a draft from the remote backend. `args` should contain an
    `inbox_uid` or a `message_id_header` key. This is used to find the draft on
    "the backend.

    """
    inbox_uid = args.get('inbox_uid')
    message_id_header = args.get('message_id_header')
    assert inbox_uid or message_id_header, 'Need at least one header value'
    remote_delete_draft(account_id, inbox_uid, message_id_header)


def save_sent_email(account_id, message_id):
    """
    Create an email on the remote backend. Generic providers expect
    us to create a copy of the message in the sent folder.
    """
    remote_save_sent(account_id, message_id)


def delete_sent_email(account_id, message_id, args):
    """
    Delete an email on the remote backend, in the sent folder.
    """
    message_id_header = args.get('message_id_header')
    assert message_id_header, 'Need the message_id_header'
    remote_delete_sent(account_id, message_id_header)
