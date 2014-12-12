# -*- coding: utf-8 -*-
""" Operations for syncing back local datastore changes to
    generic IMAP providers.

See imap.py for notes about implementation.
"""
from sqlalchemy.orm import joinedload

from inbox.crispin import writable_connection_pool, retry_crispin
from inbox.actions.backends.imap import syncback_action
from inbox.mailsync.backends.imap.generic import uidvalidity_cb
from inbox.models.backends.imap import ImapThread, ImapUid
from inbox.models.folder import Folder
from inbox.models.thread import Thread
from inbox.models.message import Message

PROVIDER = 'generic'

__all__ = ['set_remote_archived', 'set_remote_starred', 'set_remote_unread',
           'remote_save_draft', 'remote_delete_draft', 'set_remote_spam',
           'set_remote_trash']


def get_thread_uids(db_session, thread_id, namespace_id):
    """A shortcut method to get uids of the messages in a thread
    thread_id: integer
    """
    opts = joinedload('messages').joinedload('imapuids').load_only('msg_uid')
    return db_session.query(ImapThread).options(opts).filter_by(
        namespace_id=namespace_id, id=thread_id).one()


def get_imapuids_in_folder(db_session, thread_id, folder_id, account_id):
    return db_session.query(ImapUid).join(Message).filter(
        ImapUid.folder_id == folder_id,
        ImapUid.account_id == account_id,
        Message.thread_id == thread_id)


def set_remote_archived(account, thread_id, archived, db_session):
    if account.archive_folder is None:
        # account has no detected archive folder - create one.
        archive_folder = Folder.find_or_create(db_session, account,
                                               'Archive', 'archive')
        account.archive_folder = archive_folder
        db_session.commit()

    thread = db_session.query(Thread).get(thread_id)

    # FIXME @karim: not sure if we should exclude sent or not.
    folders = [folder.name for folder in thread.folders]

    if archived:
        for folder in folders:
            remote_move(account, thread_id, folder,
                        account.archive_folder.name, db_session,
                        create_destination=True)
    else:
        remote_move(account, thread_id, account.archive_folder.name,
                    account.inbox_folder.name, db_session)


def set_remote_starred(account, thread_id, starred, db_session):
    thread = db_session.query(Thread).get(thread_id)
    folders = {folder.name: folder.id for folder in thread.folders}

    for folder in folders:
        uids = get_imapuids_in_folder(db_session, thread_id,
                                      folders[folder], account.id)

        uids = [uid.msg_uid for uid in uids]

        # No need to open a connection if there's no messages to star
        if not uids:
            continue

        @retry_crispin
        def fn():
            with writable_connection_pool(account.id).get() as crispin_client:
                crispin_client.select_folder(folder, uidvalidity_cb)
                crispin_client.set_starred(uids, starred)
        fn()


def set_remote_unread(account, thread_id, unread, db_session):
    thread = db_session.query(Thread).get(thread_id)
    folders = {folder.name: folder.id for folder in thread.folders}

    for folder in folders:
        uids = get_imapuids_in_folder(db_session, thread_id,
                                      folders[folder], account.id)

        uids = [uid.msg_uid for uid in uids]

        # No need to open a connection if there's no messages from
        # this thread in the folder
        if not uids:
            continue

        @retry_crispin
        def fn():
            with writable_connection_pool(account.id).get() as crispin_client:
                crispin_client.select_folder(folder, uidvalidity_cb)
                crispin_client.set_unread(uids, unread)
        fn()


@retry_crispin
def remote_move(account, thread_id, from_folder, to_folder, db_session,
                create_destination=False):
    if from_folder == to_folder:
        return

    uids = []
    thread = get_thread_uids(db_session, thread_id, account.namespace.id)
    for msg in thread.messages:
        uids.extend([uid.msg_uid for uid in msg.imapuids])

    if not uids:
        return

    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.select_folder(from_folder, uidvalidity_cb)

        folders = crispin_client.folder_names()

        if from_folder not in folders.values() and \
           from_folder not in folders['extra']:
                raise Exception("Unknown from_folder '{}'".format(from_folder))

        if to_folder not in folders.values() and \
           to_folder not in folders['extra']:
            if create_destination:
                crispin_client.create_folder(to_folder)
            else:
                raise Exception("Unknown to_folder '{}'".format(to_folder))

        crispin_client.select_folder(from_folder, uidvalidity_cb)
        crispin_client.copy_uids(uids, to_folder)
        crispin_client.delete_uids(uids)


@retry_crispin
def remote_copy(account, thread_id, from_folder, to_folder, db_session):
    if from_folder == to_folder:
        return

    uids = []
    thread = get_thread_uids(db_session, thread_id, account.namespace.id)
    for msg in thread.messages:
        uids.extend([uid.msg_uid for uid in msg.imapuids])

    if not uids:
        return

    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.select_folder(from_folder, uidvalidity_cb)

        folders = crispin_client.folder_names()

        if from_folder not in folders.values() and \
           from_folder not in folders['extra']:
                raise Exception("Unknown from_folder '{}'".format(from_folder))

        if to_folder not in folders.values() and \
           to_folder not in folders['extra']:
                raise Exception("Unknown to_folder '{}'".format(to_folder))

        crispin_client.copy_uids(uids, to_folder)


# TODO(emfree) ensure that drafts folder exists locally and remotely for custom
# IMAP accounts.


@retry_crispin
def remote_save_draft(account, folder_name, message, db_session, date=None):
    with writable_connection_pool(account.id).get() as crispin_client:
        assert folder_name == crispin_client.folder_names()['drafts']

        crispin_client.select_folder(folder_name, uidvalidity_cb)
        crispin_client.save_draft(message, date)


@retry_crispin
def remote_delete_draft(account, inbox_uid, message_id_header, db_session):
    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.delete_draft(inbox_uid, message_id_header)


def remote_save_sent(account, folder_name, message, db_session, date=None,
                     create_backend_sent_folder=False):
    def fn(account, db_session, crispin_client):
        if create_backend_sent_folder:
            if 'sent' not in crispin_client.folder_names():
                crispin_client.create_folder('Sent')

        crispin_client.select_folder(folder_name, uidvalidity_cb)
        crispin_client.create_message(message, date)

    return syncback_action(fn, account, folder_name, db_session,
                           select_folder=False)


def set_remote_spam(account, thread_id, spam, db_session):

    if account.spam_folder is None:
        # account has no detected spam folder - create one.
        spam_folder = Folder.find_or_create(db_session, account,
                                            'Spam', 'spam')
        account.spam_folder = spam_folder
        db_session.commit()

    thread = db_session.query(Thread).get(thread_id)

    # FIXME @karim: not sure if we should exclude sent or not.
    folders = [folder.name for folder in thread.folders]

    if spam:
        for folder in folders:
            remote_move(account, thread_id, folder,
                        account.spam_folder.name, db_session,
                        create_destination=True)
        else:
            remote_move(account, thread_id, account.spam_folder.name,
                        account.inbox_folder.name, db_session)


def set_remote_trash(account, thread_id, trash, db_session):
    if account.trash_folder is None:
        # account has no detected trash folder - create one.
        trash_folder = Folder.find_or_create(db_session, account,
                                             'Trash', 'trash')
        account.trash_folder = trash_folder
        db_session.commit()

    thread = db_session.query(Thread).get(thread_id)

    # FIXME @karim: not sure if we should exclude sent or not.
    folders = [folder.name for folder in thread.folders]

    if trash:
        for folder in folders:
            remote_move(account, thread_id, folder,
                        account.trash_folder.name, db_session,
                        create_destination=True)
        else:
            remote_move(account, thread_id, account.trash_folder.name,
                        account.inbox_folder.name, db_session)
