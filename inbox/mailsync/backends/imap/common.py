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
from inbox.models.message import Message
from inbox.models.folder import Folder
from inbox.models.backends.imap import ImapUid, ImapFolderInfo

from inbox.log import get_logger
log = get_logger()


def all_uids(account_id, session, folder_name):
    return {uid for uid, in session.query(ImapUid.msg_uid).join(Folder).filter(
        ImapUid.account_id == account_id,
        Folder.name == folder_name)}


def update_thread_labels(thread, folder_name, g_labels, db_session):
    """ Make sure `thread` has all the right labels. """
    existing_labels = {folder.name.lower() for folder in thread.folders
                       if folder.name is not None} | \
                      {folder.canonical_name for folder in thread.folders
                       if folder.canonical_name is not None}

    new_labels = {l.lstrip('\\').lower() if isinstance(l, unicode)
                  else unicode(l) for l in g_labels if l is not None}
    new_labels.add(folder_name.lower())

    # Remove labels that have been deleted -- note that the \Inbox, \Sent,
    # \Important, \Starred, and \Drafts labels are per-message, not per-thread,
    # but since we always work at the thread level, _we_ apply the label to the
    # whole thread.
    # TODO: properly aggregate \Inbox, \Sent, \Important, and \Drafts
    # per-message so we can detect deletions properly.
    folders_to_discard = []
    for folder in thread.folders:
        if folder.canonical_name not in ('inbox', 'sent', 'drafts',
                                         'important', 'starred', 'all'):
            if folder.lowercase_name not in new_labels:
                folders_to_discard.append(folder)
    for folder in folders_to_discard:
        thread.folders.discard(folder)

    # add new labels
    for label in new_labels:
        if label.lower() not in existing_labels:
            # The problem here is that Gmail's attempt to squash labels and
            # IMAP folders into the same abstraction doesn't work perfectly. In
            # particular, there is a '[Gmail]/Sent' folder, but *also* a 'Sent'
            # label, and so on. We handle this by only maintaining one folder
            # object that encapsulates both of these. If a Gmail user does not
            # have these folders enabled via IMAP, we create Folder rows
            # with no 'name' attribute and fill in the 'name' if the account
            # is later reconfigured.
            canonical_labels = {
                'sent': thread.namespace.account.sent_folder,
                'draft': thread.namespace.account.drafts_folder,
                'starred': thread.namespace.account.starred_folder,
                'important': thread.namespace.account.important_folder}
            if label in canonical_labels:
                folder = canonical_labels[label]
                if folder:
                    thread.folders.add(folder)
                else:
                    folder = Folder.find_or_create(
                        db_session, thread.namespace.account, None, label)
                    thread.folders.add(folder)
            else:
                folder = Folder.find_or_create(db_session,
                                               thread.namespace.account, label)
                thread.folders.add(folder)
    return new_labels


def update_metadata(account_id, session, folder_name, uids, new_flags):
    """ Update flags (the only metadata that can change).

    Make sure you're holding a db write lock on the account. (We don't try
    to grab the lock in here in case the caller needs to put higher-level
    functionality in the lock.)
    """
    if uids:
        for item in session.query(ImapUid).join(Folder)\
                .filter(ImapUid.account_id == account_id,
                        ImapUid.msg_uid.in_(uids), Folder.name == folder_name)\
                .options(joinedload(ImapUid.message)):
            flags = new_flags[item.msg_uid].flags
            thread = item.message.thread
            if hasattr(new_flags[item.msg_uid], 'labels'):
                labels = new_flags[item.msg_uid].labels
                update_thread_labels(thread, folder_name, labels, session)
            else:
                labels = None
            item.update_imap_flags(flags, labels)

            unread_status_changed = item.message.is_read != item.is_seen

            item.message.is_draft = item.is_draft
            item.message.is_read = item.is_seen

            # We have to update the thread's read tag separately.
            if unread_status_changed:
                unread_tag = thread.namespace.tags['unread']
                if not item.message.is_read:
                    thread.apply_tag(unread_tag)
                elif all(m.is_read for m in thread.messages):
                    thread.remove_tag(unread_tag)


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

        for d in deletes:
            session.delete(d)

        for uid in deletes:
            if uid.message is not None:
                thread = uid.message.thread
                folder = uid.folder
                thread.folders.discard(folder)
        session.commit()

        # XXX TODO: Have a recurring worker permanently remove dangling
        # messages and threads from the database.


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
        return selected_uidvalidity >= cached_uidvalidity


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
    new_msg = Message(account=account, mid=msg.uid, folder_name=folder.name,
                      received_date=msg.internaldate, flags=msg.flags,
                      body_string=msg.body)

    imapuid = ImapUid(account=account, folder=folder, msg_uid=msg.uid,
                      message=new_msg)
    imapuid.update_imap_flags(msg.flags, msg.g_labels)

    new_msg.is_draft = imapuid.is_draft
    new_msg.is_read = imapuid.is_seen

    update_contacts_from_message(db_session, new_msg, account.id)

    # NOTE: This might be a good place to add FolderItem entries for
    # non-Gmail backends.

    return imapuid
