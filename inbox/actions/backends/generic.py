# -*- coding: utf-8 -*-
""" Operations for syncing back local datastore changes to
    generic IMAP providers.
"""
from collections import defaultdict
from inbox.crispin import writable_connection_pool, retry_crispin
from inbox.log import get_logger
from inbox.mailsync.backends.imap.generic import uidvalidity_cb
from inbox.models.backends.imap import ImapUid
from inbox.models.folder import Folder
from inbox.models.category import Category

log = get_logger()

PROVIDER = 'generic'

__all__ = ['set_remote_starred', 'set_remote_unread', 'remote_move',
           'remote_save_draft', 'remote_delete_draft', 'remote_create_folder',
           'remote_update_folder']

# STOPSHIP(emfree):
# * should update local UID state here after action succeeds, instead of
#   waiting for sync to pick it up
# * should add support for rolling back message.categories() on failure.


def uids_by_folder(message_id, db_session):
    results = db_session.query(ImapUid.msg_uid, Folder.name).join(Folder). \
        filter(ImapUid.message_id == message_id).all()
    mapping = defaultdict(list)
    for uid, folder_name in results:
        mapping[folder_name].append(uid)
    return mapping


@retry_crispin
def _set_flag(account, message_id, flag_name, db_session, is_add):
    uids_for_message = uids_by_folder(message_id, db_session)
    if not uids_for_message:
        log.warning('No UIDs found for message', message_id=message_id)
        return

    with writable_connection_pool(account.id).get() as crispin_client:
        for folder_name, uids in uids_for_message.items():
            crispin_client.select_folder(folder_name, uidvalidity_cb)
            if is_add:
                crispin_client.conn.add_flags(uids, [flag_name])
            else:
                crispin_client.conn.remove_flags(uids, [flag_name])


def set_remote_starred(account, message_id, db_session, starred):
    _set_flag(account, message_id, '\\Flagged', db_session, starred)


def set_remote_unread(account, message_id, db_session, unread):
    _set_flag(account, message_id, '\\Seen', db_session, not unread)


@retry_crispin
def remote_move(account, message_id, db_session, destination):
    uids_for_message = uids_by_folder(message_id, db_session)
    if not uids_for_message:
        log.warning('No UIDs found for message', message_id=message_id)
        return

    with writable_connection_pool(account.id).get() as crispin_client:
        for folder_name, uids in uids_for_message.items():
            crispin_client.select_folder(folder_name, uidvalidity_cb)
            crispin_client.conn.copy(uids, destination)
            crispin_client.delete_uids(uids)


@retry_crispin
def remote_create_folder(account, category_id, db_session):
    category = db_session.query(Category).get(category_id)
    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.conn.create_folder(category.display_name)


@retry_crispin
def remote_update_folder(account, category_id, db_session, old_name):
    category = db_session.query(Category).get(category_id)
    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.conn.rename_folder(old_name, category.display_name)


@retry_crispin
def remote_save_draft(account, message, db_session, date=None):
    with writable_connection_pool(account.id).get() as crispin_client:
        # Create drafts folder on the backend if it doesn't exist.
        if 'drafts' not in crispin_client.folder_names():
            log.info('Account has no detected drafts folder; not saving draft',
                     account_id=account.id)
            return
        folder_name = crispin_client.folder_names()['drafts'][0]
        crispin_client.select_folder(folder_name, uidvalidity_cb)
        crispin_client.save_draft(message, date)


@retry_crispin
def remote_delete_draft(account, inbox_uid, message_id_header, db_session):
    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.delete_draft(inbox_uid, message_id_header)


@retry_crispin
def remote_save_sent(account, message, date=None):
    with writable_connection_pool(account.id).get() as crispin_client:
        if 'sent' not in crispin_client.folder_names():
            log.info('Account has no detected sent folder; not saving message',
                     account_id=account.id)
            return

        folder_name = crispin_client.folder_names()['sent'][0]
        crispin_client.select_folder(folder_name, uidvalidity_cb)
        crispin_client.create_message(message, date)
