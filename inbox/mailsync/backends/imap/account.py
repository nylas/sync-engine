""" Helper functions for actions that operate on accounts.

These could be methods of ImapAccount, but separating them gives us more
flexibility with calling code, as most don't need any attributes of the account
object other than the ID, to limit the action.

Types returned for data are the column types defined via SQLAlchemy.

Eventually we're going to want a better way of ACLing functions that operate on
accounts.
"""
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from inbox.models.block import Block
from inbox.models.message import Message, SpoolMessage
from inbox.models.folder import Folder
from inbox.models.namespace import Namespace
from inbox.models.backends.imap import (ImapUid, ImapFolderInfo, ImapThread,
                                        ImapAccount)

from inbox.log import get_logger
log = get_logger()


def total_stored_data(account_id, session):
    """
    Computes the total size of the block data of emails in your
    account's IMAP folders.

    """
    subq = session.query(Block) \
        .join(Block.message, Message.imapuid) \
        .filter(ImapUid.account_id == account_id) \
        .group_by(Message.id, Block.id)
    return session.query(func.sum(subq.subquery().columns.size)).scalar()


def total_stored_messages(account_id, session):
    """ Computes the number of emails in your account's IMAP folders. """
    return session.query(Message) \
        .join(Message.imapuid) \
        .filter(ImapUid.account_id == account_id) \
        .group_by(Message.id).count()


def num_uids(account_id, session, folder_name):
    return session.query(ImapUid.msg_uid).join(Folder).filter(
        ImapUid.account_id == account_id,
        Folder.name == folder_name).count()


def all_uids(account_id, session, folder_name):
    return [uid for uid, in session.query(ImapUid.msg_uid).join(Folder).filter(
        ImapUid.account_id == account_id,
        Folder.name == folder_name)]


def g_msgids(account_id, session, in_=None):
    # Easiest way to account-filter Messages is to namespace-filter from
    # the associated thread. (Messages may not necessarily have associated
    # ImapUids.)
    query = session.query(Message.g_msgid).join(ImapThread).join(Namespace)\
        .join(ImapAccount).filter(Namespace.account_id == account_id).all()
    # in some cases, in_ can contain +100k items, when the query only
    # returns a few thousand. we shouldn't pass them all to MySQL
    in_ = {long(i) for i in in_}  # in case they are strings
    return sorted([g_msgid for g_msgid, in query if g_msgid in in_])


def g_metadata(account_id, session, folder_name):
    query = session.query(ImapUid.msg_uid, Message.g_msgid, Message.g_thrid)\
        .filter(ImapUid.account_id == account_id,
                Folder.name == folder_name,
                ImapUid.message_id == Message.id)

    return dict([(uid, dict(msgid=g_msgid, thrid=g_thrid))
                 for uid, g_msgid, g_thrid in query])


def update_thread_labels(thread, folder_name, g_labels, db_session):
    """ Make sure `thread` has all the right labels. """

    existing_labels = {folder.name.lower() for folder in thread.folders
                       if folder.name is not None} | \
                      {folder.canonical_name for folder in thread.folders
                       if folder.canonical_name is not None}
    new_labels = {l.lstrip('\\').lower() for l in g_labels}
    new_labels.add(folder_name.lower())

    # Remove labels that have been deleted -- note that the \Inbox, \Sent,
    # \Important, \Starred, and \Drafts labels are per-message, not per-thread,
    # but since we always work at the thread level, _we_ apply the label to the
    # whole thread.
    # TODO: properly aggregate \Inbox, \Sent, \Important, and \Drafts
    # per-message so we can detect deletions properly.
    thread.folders = {folder for folder in thread.folders if
                      (folder.name is not None and
                       folder.name.lower() in new_labels) or
                      folder.canonical_name in ('inbox', 'sent', 'drafts',
                                                'important', 'starred')}

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
    for item in session.query(ImapUid).join(Folder)\
            .filter(ImapUid.account_id == account_id,
                    ImapUid.msg_uid.in_(uids), Folder.name == folder_name)\
            .options(joinedload(ImapUid.message)):
        flags = new_flags[item.msg_uid].flags
        if hasattr(new_flags[item.msg_uid], 'labels'):
            labels = new_flags[item.msg_uid].labels
            thread = item.message.thread
            update_thread_labels(thread, folder_name, labels, session)
        else:
            labels = None
        item.update_imap_flags(flags, labels)
        item.message.is_draft = item.is_draft
        item.message.is_read = item.is_seen


def remove_messages(account_id, session, uids, folder):
    """ Make sure you're holding a db write lock on the account. (We don't try
        to grab the lock in here in case the caller needs to put higher-level
        functionality in the lock.)
    """
    deletes = session.query(ImapUid).join(Folder).filter(
        ImapUid.account_id == account_id,
        Folder.name == folder,
        ImapUid.msg_uid.in_(uids)).all()

    for d in deletes:
        session.delete(d)
    session.commit()

    # XXX TODO: Have a recurring worker permanently remove dangling
    # messages from the database and block store. (Probably too
    # expensive to do here.)
    # XXX TODO: This doesn't properly update threads to make sure they have
    # the correct folders associated with them, or are deleted when they no
    # longer contain any messages.


def get_folder_info(account_id, session, folder_name):
    try:
        # using .one() here may catch duplication bugs
        return session.query(ImapFolderInfo).join(Folder).filter(
            ImapFolderInfo.account_id == account_id,
            Folder.name == folder_name).one()
    except NoResultFound:
        return None


def uidvalidity_valid(account_id, session, selected_uidvalidity, folder_name,
                      cached_uidvalidity=None):
    """ Validate UIDVALIDITY on currently selected folder. """
    if cached_uidvalidity is None:
        cached_uidvalidity = get_folder_info(account_id, session,
                                             folder_name).uidvalidity
        assert type(cached_uidvalidity) == type(selected_uidvalidity), \
            "cached_validity: {0} / selected_uidvalidity: {1}".format(
                type(cached_uidvalidity),
                type(selected_uidvalidity))

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

    msg_class = SpoolMessage if msg.created else Message
    new_msg = msg_class(account=account, mid=msg.uid, folder_name=folder.name,
                        received_date=msg.internaldate, flags=msg.flags,
                        body_string=msg.body)

    imapuid = ImapUid(account=account, folder=folder, msg_uid=msg.uid,
                      message=new_msg)
    imapuid.update_imap_flags(msg.flags, msg.g_labels)

    new_msg.is_draft = imapuid.is_draft
    new_msg.is_read = imapuid.is_seen

    # NOTE: This might be a good place to add FolderItem entries for
    # non-Gmail backends.

    return imapuid
