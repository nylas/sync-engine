""" Helper functions for actions that operate on accounts.

These could be methods of ImapAccount, but separating them gives us more
flexibility with calling code, as most don't need any attributes of the account
object other than the ID, to limit the action.

Types returned for data are the column types defined via SQLAlchemy.

Eventually we're going to want a better way of ACLing functions that operate on
accounts.
"""
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from inbox.contacts.process_mail import update_contacts_from_message
from inbox.models import Message, Folder
from inbox.models.backends.imap import ImapUid, ImapFolderInfo
from inbox.models.util import reconcile_message

from inbox.log import get_logger
log = get_logger()


def all_uids(account_id, session, folder_name):
    return {uid for uid, in session.query(ImapUid.msg_uid).join(Folder).filter(
        ImapUid.account_id == account_id,
        Folder.name == folder_name)}


def _folders_for_labels(g_labels, account, db_session):
    """Given a set of Gmail label strings, return the set of associated Folder
    objects. Creates new (un-added, uncommitted) Folder instances if needed."""
    # Elements of g_labels may not have unicode type (in particular, if you
    # have a numeric label, e.g., '42'), so we need to coerce to unicode.
    labels = {unicode(l).lstrip('\\').lower() for l in g_labels}

    # The problem here is that Gmail's attempt to squash labels and
    # IMAP folders into the same abstraction doesn't work perfectly. In
    # particular, there is a '[Gmail]/Sent' folder, but *also* a 'Sent'
    # label, and so on. We handle this by only maintaining one folder
    # object that encapsulates both of these. If a Gmail user does not
    # have these folders enabled via IMAP, we create Folder rows
    # with no 'name' attribute and fill in the 'name' if the account
    # is later reconfigured.
    special_folders = {
        'inbox': account.inbox_folder,
        'sent': account.sent_folder,
        'draft': account.drafts_folder,
        'starred': account.starred_folder,
        'important': account.important_folder,
    }

    folders = set()
    for label in labels:
        if label in special_folders:
            folder = special_folders[label]
            if folder is None:
                folder = Folder.find_or_create(db_session, account, None,
                                               label)
            folders.add(folder)
        else:
            folders.add(
                Folder.find_or_create(db_session, account, label))
    return folders


def add_any_new_thread_labels(thread, new_uid, db_session):
    """Update the folders associated with a thread when a new uid is synced for
    it."""
    thread.folders.add(new_uid.folder)
    if new_uid.g_labels is not None:
        folders_for_labels = _folders_for_labels(
            new_uid.g_labels, thread.namespace.account, db_session)
        for folder in folders_for_labels:
            thread.folders.add(folder)


def recompute_thread_labels(thread, db_session):
    """Aggregate folders and labels for a thread's Imapuids, and make sure the
    thread has the right folders associated with it."""
    g_labels = set()
    expected_folders = set()
    for message in thread.messages:
        for uid in message.imapuids:
            if uid.g_labels is not None:
                g_labels.update(uid.g_labels)
            expected_folders.add(uid.folder)

    folders_for_labels = _folders_for_labels(
        g_labels, thread.namespace.account, db_session)
    expected_folders.update(folders_for_labels)

    for folder in set(thread.folders):
        if folder not in expected_folders:
            thread.folders.discard(folder)

    for folder in expected_folders:
        thread.folders.add(folder)


def update_metadata(account_id, session, folder_name, folder_id, uids,
                    new_flags):
    """
    Update flags and labels (the only metadata that can change).

    Make sure you're holding a db write lock on the account. (We don't try
    to grab the lock in here in case the caller needs to put higher-level
    functionality in the lock.)

    """
    affected_threads = set()
    if uids:
        for item in session.query(ImapUid). \
                filter(ImapUid.account_id == account_id,
                       ImapUid.msg_uid.in_(uids),
                       ImapUid.folder_id == folder_id). \
                options(joinedload(ImapUid.message)):
            flags = new_flags[item.msg_uid].flags
            thread = item.message.thread
            affected_threads.add(thread)
            if hasattr(new_flags[item.msg_uid], 'labels'):  # i.e: gmail
                labels = new_flags[item.msg_uid].labels
                item.g_labels = [label for label in labels]
            else:
                labels = None
            item.update_imap_flags(flags, labels)

            unread_status_changed = item.message.is_read != item.is_seen
            draft_status_changed = item.message.is_draft != item.is_draft

            item.message.is_draft = item.is_draft
            item.message.is_read = item.is_seen

            # We have to update the thread's read tag separately.
            if unread_status_changed:
                unread_tag = thread.namespace.tags['unread']
                if not item.message.is_read:
                    thread.apply_tag(unread_tag)
                elif all(m.is_read for m in thread.messages):
                    thread.remove_tag(unread_tag)

            if draft_status_changed:
                if not item.is_draft:
                    item.message.state = 'sent'
                else:
                    item.message.state = 'draft'

        for thread in affected_threads:
            recompute_thread_labels(thread, session)


def remove_messages(account_id, session, uids, folder):
    """ Make sure you're holding a db write lock on the account. (We don't try
        to grab the lock in here in case the caller needs to put higher-level
        functionality in the lock.)
    """
    if uids:
        deletes = session.query(ImapUid).join(Folder).filter(
            ImapUid.account_id == account_id,
            Folder.name == folder,
            ImapUid.msg_uid.in_(uids)).all()

        # Remove message if he has no associated UIDs.
        # This may cause the message to disappear transiently
        # when moved between folders. The delay should be short
        # enough to be unnoticeable.
        #
        # FIXME @karim: we shouldn't be deleting messages --
        # the clean way to handle this problem is have a daemon
        # detect "dangling" threads and messages and collect
        # them periodically (tracked in T477)
        affected_messages = {uid.message for uid in deletes
                             if uid.message is not None}

        for uid in deletes:
            session.delete(uid)
        session.commit()

        messages_to_delete = {m for m in affected_messages if not m.imapuids}

        # Because we need to update thread folders and tags, threads are
        # 'affected' even if we're not removing messages from them.
        affected_threads = {m.thread for m in affected_messages}

        for message in messages_to_delete:
            session.delete(message)
        session.commit()

        for thread in affected_threads:
            if not thread.messages:
                session.delete(thread)
            else:
                recompute_thread_labels(thread, session)

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
    """ IMAP-specific message creation logic.

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
    new_msg = Message.create_from_synced(account=account, mid=msg.uid,
                                         folder_name=folder.name,
                                         received_date=msg.internaldate,
                                         body_string=msg.body)

    # Check to see if this is a copy of a message that was first created
    # by the Inbox API. If so, don't create a new object; just use the old one.
    existing_copy = reconcile_message(new_msg, db_session)
    if existing_copy is not None:
        new_msg = existing_copy

    imapuid = ImapUid(account=account, folder=folder, msg_uid=msg.uid,
                      message=new_msg)
    imapuid.update_imap_flags(msg.flags, msg.g_labels)

    new_msg.is_draft = imapuid.is_draft
    if imapuid.is_draft:
        new_msg.state = 'draft'
    new_msg.is_read = imapuid.is_seen

    update_contacts_from_message(db_session, new_msg, account.namespace)

    return imapuid
