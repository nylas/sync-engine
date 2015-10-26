""" Operations for syncing back local datastore changes to Gmail. """

import imapclient
from inbox.crispin import writable_connection_pool
from inbox.actions.backends.generic import (set_remote_starred,
                                            set_remote_unread,
                                            remote_delete_draft,
                                            remote_update_draft,
                                            remote_save_draft,
                                            uids_by_folder)
from inbox.mailsync.backends.imap.generic import uidvalidity_cb
from inbox.models.category import Category
from imaplib import IMAP4

PROVIDER = 'gmail'

__all__ = ['set_remote_starred', 'set_remote_unread', 'remote_save_draft',
           'remote_update_draft', 'remote_change_labels',
           'remote_delete_draft', 'remote_create_label', 'remote_update_label',
           'remote_delete_label']


def _encode_labels(labels):
    return map(imapclient.imap_utf7.encode, labels)


def remote_change_labels(account, message_id, db_session, removed_labels,
                         added_labels):
    uids_for_message = uids_by_folder(message_id, db_session)
    with writable_connection_pool(account.id).get() as crispin_client:
        for folder_name, uids in uids_for_message.items():
            crispin_client.select_folder(folder_name, uidvalidity_cb)
            crispin_client.conn.add_gmail_labels(
                uids, _encode_labels(added_labels))
            crispin_client.conn.remove_gmail_labels(
                uids, _encode_labels(removed_labels))


def remote_create_label(account, category_id, db_session):
    category = db_session.query(Category).get(category_id)
    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.conn.create_folder(category.display_name)


def remote_update_label(account, category_id, db_session, old_name):
    category = db_session.query(Category).get(category_id)
    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.conn.rename_folder(old_name, category.display_name)


def remote_delete_label(account, category_id, db_session):
    category = db_session.query(Category).get(category_id)
    with writable_connection_pool(account.id).get() as crispin_client:
        try:
            crispin_client.conn.delete_folder(category.display_name)
        except IMAP4.error:
            # Label has already been deleted on remote. Treat delete as
            # no-op.
            pass
    db_session.delete(category)
    db_session.commit()
