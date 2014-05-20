""" Gmail-specific local datastore operations.

Handles Gmail's special semantics involving "All Mail".
"""
from sqlalchemy.orm.exc import NoResultFound
from inbox.server.models.tables.base import FolderItem, Folder, Thread

from inbox.server.models.namespace import db_write_lock


class LocalActionError(Exception):
    pass


def local_archive(db_session, account, thread_id):
    """ Archive thread in the local datastore (*not* the account backend).

    (Just removes it from Inbox!)

    Idempotent.
    """
    with db_write_lock(account.namespace.id):
        try:
            inbox_item = db_session.query(FolderItem).join(Thread).filter(
                Thread.namespace_id == account.namespace.id,
                FolderItem.thread_id == thread_id,
                FolderItem.folder_id == account.inbox_folder_id).one()
            db_session.delete(inbox_item)
        except NoResultFound:
            pass
        db_session.commit()


def set_local_unread(db_session, account, thread, unread):
    with db_write_lock(account.namespace.id):
        for message in thread.messages:
            message.is_read = not unread


def local_move(db_session, account, thread_id, from_folder, to_folder):
    """ Move thread in the local datastore (*not* the account backend).

    NOT idempotent.
    """
    if from_folder == to_folder:
        return

    with db_write_lock(account.namespace.id):
        listings = {item.folder.name: item for item in
                    db_session.query(FolderItem).join(Folder).join(Thread)
                    .filter(
                        Thread.namespace_id == account.namespace.id,
                        FolderItem.thread_id == thread_id,
                        Folder.name.in_([from_folder, to_folder]))
                    .all()}
        if from_folder not in listings:
            raise LocalActionError("thread {} does not exist in folder {}"
                                   .format(thread_id, from_folder))
        elif to_folder not in listings:
            folder = Folder.find_or_create(db_session, account, to_folder)
            listings[from_folder].folder = folder
            db_session.commit()


def local_copy(db_session, account, thread_id, from_folder, to_folder):
    """ Copy thread in the local datastore (*not* the account backend).

    NOT idempotent.
    """
    if from_folder == to_folder:
        return

    with db_write_lock(account.namespace.id):
        listings = {item.folder.name: item for item in
                    db_session.query(FolderItem).join(Folder).join(Thread)
                    .filter(
                        Thread.namespace_id == account.namespace.id,
                        FolderItem.thread_id == thread_id,
                        Folder.name.in_([from_folder, to_folder]))
                    .all()}
        if from_folder not in listings:
            raise LocalActionError("thread {} does not exist in folder {}"
                                   .format(thread_id, from_folder))
        elif to_folder not in listings:
            thread = listings[from_folder].thread
            folder = Folder.find_or_create(db_session,
                                           thread.namespace.account,
                                           to_folder)
            thread.folders.add(folder)
            db_session.commit()


def local_delete(db_session, account, thread_id, folder_name):
    """ Delete thread in the local datastore (*not* the account backend).

    NOT idempotent. (Will throw an exception if the thread doesn't exist in
    `folder_name`.)
    """
    with db_write_lock(account.namespace.id):
        try:
            item = db_session.query(FolderItem).join(Folder).join(Thread)\
                .filter(Thread.namespace_id == account.namespace.id,
                        FolderItem.thread_id == thread_id,
                        Folder.name == folder_name).one()
            db_session.delete(item)
            db_session.commit()
        except NoResultFound:
            raise LocalActionError("thread {} does not exist in folder {}"
                                   .format(thread_id, folder_name))
