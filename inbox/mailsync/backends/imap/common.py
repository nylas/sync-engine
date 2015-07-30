"""
Helper functions for actions that operate on accounts.

These could be methods of ImapAccount, but separating them gives us more
flexibility with calling code, as most don't need any attributes of the account
object other than the ID, to limit the action.

Types returned for data are the column types defined via SQLAlchemy.

Eventually we're going to want a better way of ACLing functions that operate on
accounts.

"""
from sqlalchemy.orm.exc import NoResultFound

from inbox.contacts.process_mail import update_contacts_from_message
from inbox.models import Message, Folder
from inbox.models.backends.imap import ImapUid, ImapFolderInfo
from inbox.models.util import reconcile_message

from inbox.log import get_logger
log = get_logger()


def all_uids(account_id, session, folder_id):
    return {uid for uid, in session.query(ImapUid.msg_uid).filter(
        ImapUid.account_id == account_id,
        ImapUid.folder_id == folder_id)}


def update_message_metadata(session, imapuid):
    # Update the message's metadata.
    imapuid.message.update_metadata(imapuid.is_draft)


def update_metadata(account_id, session, folder_name, folder_id, uids,
                    new_flags):
    """
    Update flags and labels (the only metadata that can change).

    Make sure you're holding a db write lock on the account. (We don't try
    to grab the lock in here in case the caller needs to put higher-level
    functionality in the lock.)

    """
    if not uids:
        return

    for item in session.query(ImapUid).filter(
            ImapUid.account_id == account_id,
            ImapUid.msg_uid.in_(uids),
            ImapUid.folder_id == folder_id):
        flags = new_flags[item.msg_uid].flags
        labels = getattr(new_flags[item.msg_uid], 'labels', None)

        # STOPSHIP(emfree) refactor
        changed = item.update_flags(flags)
        if labels is not None:
            item.update_labels(labels)
            changed = True

        if changed:
            update_message_metadata(session, item)


def remove_deleted_uids(account_id, session, uids, folder_id):
    """
    Make sure you're holding a db write lock on the account. (We don't try
    to grab the lock in here in case the caller needs to put higher-level
    functionality in the lock.)

    """
    if uids:
        deletes = session.query(ImapUid).filter(
            ImapUid.account_id == account_id,
            ImapUid.folder_id == folder_id,
            ImapUid.msg_uid.in_(uids)).all()
        affected_messages = {uid.message for uid in deletes
                             if uid.message is not None}

        for uid in deletes:
            session.delete(uid)
        session.commit()

        for message in affected_messages:
            if not message.imapuids and message.is_draft:
                # Synchronously delete drafts.
                session.delete(message)
            else:
                message.update_metadata(message.is_draft)
                if not message.imapuids:
                    # But don't outright delete messages. Just mark them as
                    # 'deleted' and wait for the asynchronous
                    # dangling-message-collector to delete them.
                    message.mark_for_deletion()

        session.commit()


def get_folder_info(account_id, session, folder_name):
    try:
        # using .one() here may catch duplication bugs
        return session.query(ImapFolderInfo).join(Folder).filter(
            ImapFolderInfo.account_id == account_id,
            Folder.name == folder_name).one()
    except NoResultFound:
        return None


def uidvalidity_valid(account_id, selected_uidvalidity, folder_name,
                      cached_uidvalidity):
    """ Validate UIDVALIDITY on currently selected folder. """
    if cached_uidvalidity is None:
        # no row is basically equivalent to UIDVALIDITY == -inf
        return True
    else:
        return selected_uidvalidity <= cached_uidvalidity


def update_folder_info(account_id, session, folder_name, uidvalidity,
                       highestmodseq):
    cached_folder_info = get_folder_info(account_id, session, folder_name)
    if cached_folder_info is None:
        folder = session.query(Folder).filter_by(account_id=account_id,
                                                 name=folder_name).one()
        cached_folder_info = ImapFolderInfo(account_id=account_id,
                                            folder=folder)
    cached_folder_info.highestmodseq = highestmodseq
    cached_folder_info.uidvalidity = uidvalidity
    session.add(cached_folder_info)
    return cached_folder_info


def create_imap_message(db_session, log, account, folder, msg):
    """
    IMAP-specific message creation logic.

    This is the one function in this file that gets to take an account
    object instead of an account_id, because we need to relate the
    account to ImapUids for versioning to work, since it needs to look
    up the namespace.

    Returns
    -------
    imapuid : inbox.models.tables.imap.ImapUid
        New db object, which links to new Message and Block objects through
        relationships. All new objects are uncommitted.

    """
    new_message = Message.create_from_synced(account=account, mid=msg.uid,
                                             folder_name=folder.name,
                                             received_date=msg.internaldate,
                                             body_string=msg.body)

    # Check to see if this is a copy of a message that was first created
    # by the Inbox API. If so, don't create a new object; just use the old one.
    existing_copy = reconcile_message(new_message, db_session)
    if existing_copy is not None:
        new_message = existing_copy

    imapuid = ImapUid(account=account, folder=folder, msg_uid=msg.uid,
                      message=new_message)
    imapuid.update_flags(msg.flags)
    if msg.g_labels is not None:
        imapuid.update_labels(msg.g_labels)

    # Update the message's metadata
    with db_session.no_autoflush:
        new_message.update_metadata(imapuid.is_draft)

    update_contacts_from_message(db_session, new_message, account.namespace)

    return imapuid
