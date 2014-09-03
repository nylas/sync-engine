# -*- coding: utf-8 -*-
""" Operations for syncing back local datastore changes to Yahoo.

See imap.py for notes about implementation.
"""
from sqlalchemy.orm import joinedload

from inbox.actions.backends.imap import uidvalidity_cb, syncback_action
from inbox.models.backends.imap import ImapThread
from inbox.models.message import Message
from inbox.models.folder import Folder

PROVIDER = 'generic'

__all__ = ['set_remote_archived', 'set_remote_starred', 'set_remote_unread',
           'remote_save_draft', 'remote_delete_draft', 'remote_delete']


def get_thread_uids(db_session, thread_id):
    """A shortcut method to get uids of the messages in a thread
    thread_id: integer
    """
    opts = joinedload('messages').joinedload('imapuids').load_only('msg_uid')
    return db_session.query(ImapThread).options(opts)\
        .filter_by(id=thread_id).one()


def set_remote_archived(account, thread_id, archived, db_session):
    if account.archive_folder is None:
        # account has no detected archive folder - create one.
        archive_folder = Folder.find_or_create(db_session, account,
                                               'Archive', 'archive')
        account.archive_folder = archive_folder

    if archived:
        return remote_move(account, thread_id, account.inbox_folder.name,
                           account.archive_folder.name, db_session,
                           create_destination=True)
    else:
        return remote_move(account, thread_id, account.archive_folder.name,
                           account.inbox_folder.name, db_session)


def set_remote_starred(account, thread_id, starred, db_session):
    def fn(account, db_session, crispin_client):
        uids = []

        thread = get_thread_uids(db_session, thread_id)
        for msg in thread.messages:
            uids.extend([uid.msg_uid for uid in msg.imapuids])

        crispin_client.set_starred(uids, starred)

    return syncback_action(fn, account, account.inbox_folder.name, db_session)


def set_remote_unread(account, thread_id, unread, db_session):
    def fn(account, db_session, crispin_client):
        uids = []

        thread = get_thread_uids(db_session, thread_id)
        for msg in thread.messages:
            uids.extend([uid.msg_uid for uid in msg.imapuids])
        crispin_client.set_unread(uids, unread)

    return syncback_action(fn, account, account.inbox_folder.name, db_session)


def remote_move(account, thread_id, from_folder, to_folder, db_session,
                create_destination=False):
    if from_folder == to_folder:
        return

    def fn(account, db_session, crispin_client):
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
        uids = []

        thread = get_thread_uids(db_session, thread_id)
        for msg in thread.messages:
            uids.extend([uid.msg_uid for uid in msg.imapuids])

        crispin_client.copy_uids(uids, to_folder)
        crispin_client.delete_uids(uids)

    return syncback_action(fn, account, from_folder, db_session)


def remote_copy(account, thread_id, from_folder, to_folder, db_session):
    if from_folder == to_folder:
        return

    def fn(account, db_session, crispin_client):
        uids = []
        folders = crispin_client.folder_names()

        if from_folder not in folders.values() and \
           from_folder not in folders['extra']:
                raise Exception("Unknown from_folder '{}'".format(from_folder))

        if to_folder not in folders.values() and \
           to_folder not in folders['extra']:
                raise Exception("Unknown to_folder '{}'".format(to_folder))

        thread = get_thread_uids(db_session, thread_id)
        for msg in thread.messages:
            uids.extend([uid.msg_uid for uid in msg.imapuids])

        crispin_client.copy_uids(uids, to_folder)

    return syncback_action(fn, account, from_folder, db_session)


def remote_delete(account, thread_id, folder_name, db_session):
    """ We currently only allow this for Drafts. """
    def fn(account, db_session, crispin_client):
        if folder_name == crispin_client.folder_names()['drafts']:
            uids = []

            thread = get_thread_uids(db_session, thread_id)
            for msg in thread.messages:
                uids.extend([uid.msg_uid for uid in msg.imapuids])

            crispin_client.delete_uids(uids)

    return syncback_action(fn, account, folder_name, db_session)


def remote_save_draft(account, folder_name, message, db_session, date=None):
    def fn(account, db_session, crispin_client):
        assert folder_name == crispin_client.folder_names()['drafts']
        crispin_client.save_draft(message, date)

    return syncback_action(fn, account, folder_name, db_session)


def remote_delete_draft(account, folder_name, inbox_uid, db_session):
    def fn(account, db_session, crispin_client):
        assert folder_name == crispin_client.folder_names()['drafts']
        message = db_session.query(Message).filter_by(
            public_id=inbox_uid).one()
        uids = []

        if message.resolved_message is not None:
            for imapuid in message.resolved_message.imapuids:
                uids.append(imapuid.msg_uid)

        if uids != []:
            crispin_client.delete_uids(uids)

    return syncback_action(fn, account, folder_name, db_session)
