""" Gmail-specific local datastore operations.

Handles Gmail's special semantics involving "All Mail".
"""
from sqlalchemy.orm.exc import NoResultFound

from inbox.server.models.tables.base import FolderItem, Folder, Thread
from inbox.server.models.namespace import db_write_lock
from inbox.server.crispin import RawMessage
from inbox.server.mailsync.backends.base import create_db_objects, commit_uids
from inbox.server.mailsync.backends.gmail import create_gmail_message


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


def local_save_draft(db_session, log, account_id, drafts_folder, draftmsg):
    """
    Save the draft email message to the local data store.

    Notes
    -----
    The message is stored as a SpoolMessage.

    """
    msg = RawMessage(uid=draftmsg.uid, internaldate=draftmsg.date,
                     flags=draftmsg.flags, body=draftmsg.msg, g_thrid=None,
                     g_msgid=None, g_labels=set(), created=True)

    new_uids = create_db_objects(account_id, db_session, log,
                                 drafts_folder, [msg],
                                 create_gmail_message)

    assert len(new_uids) == 1
    new_uid = new_uids[0]

    new_uid.created_date = draftmsg.date

    # Set SpoolMessage's special draft attributes
    new_uid.message.state = 'draft'
    new_uid.message.parent_draft = draftmsg.original_draft
    new_uid.message.replyto_thread_id = draftmsg.reply_to

    commit_uids(db_session, log, new_uids)

    return new_uid
