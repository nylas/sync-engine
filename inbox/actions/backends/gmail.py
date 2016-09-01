""" Operations for syncing back local datastore changes to Gmail. """

import imapclient
from inbox.actions.backends.generic import uids_by_folder
from inbox.mailsync.backends.imap.generic import uidvalidity_cb
from inbox.models.category import Category
from inbox.models.session import session_scope
from imaplib import IMAP4

PROVIDER = 'gmail'

__all__ = ['remote_create_label', 'remote_update_label', 'remote_delete_label']


def _encode_labels(labels):
    return map(imapclient.imap_utf7.encode, labels)


def remote_change_labels(crispin_client, account_id, message_id,
                         removed_labels, added_labels):
    with session_scope(account_id) as db_session:
        uids_for_message = uids_by_folder(message_id, db_session)

    for folder_name, uids in uids_for_message.items():
        crispin_client.select_folder_if_necessary(folder_name, uidvalidity_cb)
        if len(added_labels) > 0:
            crispin_client.conn.add_gmail_labels(
                uids, _encode_labels(added_labels), silent=True)
        if len(removed_labels) > 0:
            crispin_client.conn.remove_gmail_labels(
                uids, _encode_labels(removed_labels), silent=True)


def remote_create_label(crispin_client, account_id, category_id):
    with session_scope(account_id) as db_session:
        category = db_session.query(Category).get(category_id)
        if category is None:
            return
        display_name = category.display_name
    crispin_client.conn.create_folder(display_name)


def remote_update_label(crispin_client, account_id, category_id, old_name,
                        new_name):
    crispin_client.conn.rename_folder(old_name, new_name)


def remote_delete_label(crispin_client, account_id, category_id):
    with session_scope(account_id) as db_session:
        category = db_session.query(Category).get(category_id)
        if category is None:
            return
        display_name = category.display_name

    try:
        crispin_client.conn.delete_folder(display_name)
    except IMAP4.error:
        # Label has already been deleted on remote. Treat delete as
        # no-op.
        pass

    # TODO @karim --- the main sync loop has a hard time detecting
    # Gmail renames because of a Gmail issue (see https://github.com/nylas/sync-engine/blob/c99656df3c048faf7951e54d74cb5ef9d7dc3c97/inbox/mailsync/gc.py#L146 for more details).
    # Fix the problem and then remove the following shortcut.
    with session_scope(account_id) as db_session:
        category = db_session.query(Category).get(category_id)
        db_session.delete(category)
        db_session.commit()
