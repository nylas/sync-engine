"""
Helper functions for actions that operate on accounts.

These could be methods of ImapAccount, but separating them gives us more
flexibility with calling code, as most don't need any attributes of the account
object other than the ID, to limit the action.

Types returned for data are the column types defined via SQLAlchemy.

Eventually we're going to want a better way of ACLing functions that operate on
accounts.

"""
from datetime import datetime

from sqlalchemy import bindparam, desc
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import func

from inbox.contacts.process_mail import update_contacts_from_message
from inbox.models import Account, Message, Folder, ActionLog
from inbox.models.backends.imap import ImapUid, ImapFolderInfo
from inbox.models.util import reconcile_message
from inbox.sqlalchemy_ext.util import bakery
from nylas.logging import get_logger
log = get_logger()


def local_uids(account_id, session, folder_id, limit=None):
    q = bakery(lambda session: session.query(ImapUid.msg_uid))
    q += lambda q: q.filter(
        ImapUid.account_id == bindparam('account_id'),
        ImapUid.folder_id == bindparam('folder_id'))
    if limit:
        q += lambda q: q.order_by(desc(ImapUid.msg_uid))
        q += lambda q: q.limit(bindparam('limit'))
    results = q(session).params(account_id=account_id,
                                folder_id=folder_id,
                                limit=limit).all()
    return {u for u, in results}


def lastseenuid(account_id, session, folder_id):
    q = bakery(lambda session: session.query(func.max(ImapUid.msg_uid)))
    q += lambda q: q.filter(
        ImapUid.account_id == bindparam('account_id'),
        ImapUid.folder_id == bindparam('folder_id'))
    res = q(session).params(account_id=account_id,
                            folder_id=folder_id).one()[0]
    return res or 0


def update_message_metadata(session, account, message, is_draft):
    # Update the message's metadata.
    uids = message.imapuids

    message.is_read = any(i.is_seen for i in uids)
    message.is_starred = any(i.is_flagged for i in uids)
    message.is_draft = is_draft

    categories = set()
    for i in uids:
        categories.update(i.categories)

    if account.category_type == 'folder':
        categories = [_select_category(categories)] if categories else []

    if not message.categories_changes:
        # No syncback actions scheduled, so there is no danger of
        # overwriting modified local state.
        message.categories = categories
    else:
        _update_categories(session, message, categories)


def update_metadata(account_id, folder_id, new_flags, session):
    """
    Update flags and labels (the only metadata that can change).

    Make sure you're holding a db write lock on the account. (We don't try
    to grab the lock in here in case the caller needs to put higher-level
    functionality in the lock.)

    """
    if not new_flags:
        return

    account = Account.get(account_id, session)
    change_count = 0
    for item in session.query(ImapUid).filter(
            ImapUid.account_id == account_id,
            ImapUid.msg_uid.in_(new_flags.keys()),
            ImapUid.folder_id == folder_id):
        flags = new_flags[item.msg_uid].flags
        labels = getattr(new_flags[item.msg_uid], 'labels', None)

        # TODO(emfree) refactor so this is only ever relevant for Gmail.
        changed = item.update_flags(flags)
        if labels is not None:
            item.update_labels(labels)
            changed = True

        if changed:
            change_count += 1
            update_message_metadata(session, account, item.message,
                                    item.is_draft)
            session.commit()
    log.info('Updated UID metadata', changed=change_count,
             out_of=len(new_flags))


def remove_deleted_uids(account_id, folder_id, uids, session):
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
                thread = message.thread
                thread.messages.remove(message)
                session.delete(message)
                if not thread.messages:
                    session.delete(thread)
            else:
                account = Account.get(account_id, session)
                update_message_metadata(session, account, message,
                                        message.is_draft)
                if not message.imapuids:
                    # But don't outright delete messages. Just mark them as
                    # 'deleted' and wait for the asynchronous
                    # dangling-message-collector to delete them.
                    message.mark_for_deletion()
            session.commit()

        log.info('Deleted expunged UIDs', count=len(deletes))


def get_folder_info(account_id, session, folder_name):
    try:
        # using .one() here may catch duplication bugs
        return session.query(ImapFolderInfo).join(Folder).filter(
            ImapFolderInfo.account_id == account_id,
            Folder.name == folder_name).one()
    except NoResultFound:
        return None


def create_imap_message(db_session, account, folder, msg):
    """
    IMAP-specific message creation logic.

    Returns
    -------
    imapuid : inbox.models.backends.imap.ImapUid
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
        update_message_metadata(db_session, account, new_message,
                                imapuid.is_draft)

    update_contacts_from_message(db_session, new_message, account.namespace)

    return imapuid


def _select_category(categories):
    # TODO[k]: Implement proper ranking function
    return list(categories)[0]


def _update_categories(db_session, message, synced_categories):
    now = datetime.utcnow()

    # We make the simplifying assumption that only the latest syncback action
    # matters, since it reflects the current local state.
    actionlog_id = db_session.query(func.max(ActionLog.id)).filter(
        ActionLog.namespace_id == message.namespace_id,
        ActionLog.table_name == 'message',
        ActionLog.record_id == message.id,
        ActionLog.action.in_(['change_labels', 'move'])).scalar()
    actionlog = db_session.query(ActionLog).get(actionlog_id)

    # We completed the syncback action /long enough ago/ (on average and
    # with an error margin) that:
    # - if it completed successfully, sync has picked it up; so, safe to
    # overwrite message.categories
    # - if syncback failed, the local changes made can be overwritten
    # without confusing the API user.
    # TODO[k]/(emfree): Implement proper rollback of local state in this case.
    # This is needed in order to pick up future changes to the message,
    # the local_changes counter is reset as well.
    if actionlog.status in ('successful', 'failed') and \
            (now - actionlog.updated_at).seconds >= 90:
        message.categories = synced_categories
        message.categories_changes = False

    # Do /not/ overwrite message.categories in case of a recent local change -
    # namely, a still 'pending' action or one that completed recently.
