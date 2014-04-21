""" Helper functions for actions that operate on accounts.

These could be methods of ImapAccount, but separating them gives us more
flexibility with calling code, as most don't need any attributes of the account
object other than the ID, to limit the action.

Eventually we're going to want a better way of ACLing functions that operate on
accounts.
"""
from sqlalchemy import distinct, func
from sqlalchemy.orm.exc import NoResultFound

from inbox.server.mailsync.hooks import default_hook_manager
from inbox.server.models.tables.base import Block, Message, FolderItem
from inbox.server.models.tables.imap import ImapUid, UIDValidity, ImapThread
from inbox.server.models.message import create_message, reconcile_message

from inbox.server.log import get_logger
log = get_logger()


def total_stored_data(account_id, session):
    """ Computes the total size of the block data of emails in your
        account's IMAP folders
    """
    subq = session.query(Block) \
        .join(Block.message, Message.imapuid) \
        .filter(ImapUid.imapaccount_id == account_id) \
        .group_by(Message.id, Block.id)
    return int(session.query(func.sum(subq.subquery().columns.size)).scalar())


def total_stored_messages(account_id, session):
    """ Computes the number of emails in your account's IMAP folders """
    return session.query(Message) \
        .join(Message.imapuid) \
        .filter(ImapUid.imapaccount_id == account_id) \
        .group_by(Message.id).count()


def all_uids(account_id, session, folder_name):
    return [uid for uid, in
            session.query(ImapUid.msg_uid).filter_by(
                imapaccount_id=account_id, folder_name=folder_name)]


def g_msgids(account_id, session, in_=None):
    query = session.query(distinct(Message.g_msgid)).join(ImapUid) \
        .filter(ImapUid.imapaccount_id == account_id)
    if in_ is not None and len(in_):
        in_ = [int(i) for i in in_]  # very slow if we send non-integers
        query = query.filter(Message.g_msgid.in_(in_))
    return sorted([g_msgid for g_msgid, in query], key=long)


def g_metadata(account_id, session, folder_name):
    query = session.query(ImapUid.msg_uid, Message.g_msgid, Message.g_thrid)\
        .filter(ImapUid.imapaccount_id == account_id,
                ImapUid.folder_name == folder_name,
                ImapUid.message_id == Message.id)

    return dict([(int(uid), dict(msgid=g_msgid, thrid=g_thrid))
                 for uid, g_msgid, g_thrid in query])


def update_metadata(account_id, session, folder_name, uids, new_flags):
    """ Update flags (the only metadata that can change).

    Make sure you're holding a db write lock on the account. (We don't try
    to grab the lock in here in case the caller needs to put higher-level
    functionality in the lock.)
    """
    # The join here means we won't update flags on messages that have been
    # deleted locally (but the delete hasn't propagated yet), That's A-OK: that
    # delete will eventually be synced back to the account backend, so it
    # doesn't matter if our flags get out-of-date in the meantime.
    for item in session.query(ImapUid).join(Message).filter(
            ImapUid.imapaccount_id == account_id,
            ImapUid.msg_uid.in_(uids),
            ImapUid.folder_name == folder_name):
        flags = new_flags[item.msg_uid]['flags']
        labels = new_flags[item.msg_uid]['labels']
        item.update_imap_flags(flags, labels)
        item.message.is_draft = item.is_draft
        # NOTE: If we're ever going to make our datastore API support "read"
        # status, this is the place to put update of that flag.
        # (is_seen == is_read)


def remove_messages(account_id, session, uids, folder):
    """ Make sure you're holding a db write lock on the account. (We don't try
        to grab the lock in here in case the caller needs to put higher-level
        functionality in the lock.)
    """
    deletes = session.query(ImapUid).filter(
        ImapUid.imapaccount_id == account_id,
        ImapUid.folder_name == folder,
        ImapUid.msg_uid.in_(uids)).all()

    for d in deletes:
        session.delete(d)

    # XXX TODO: Have a recurring worker permanently remove dangling
    # messages from the database and block store. (Probably too
    # expensive to do here.)
    # XXX TODO: This doesn't properly update threads to make sure they have
    # the correct folders associated with them, or are deleted when they no
    # longer contain any messages.


def get_uidvalidity(account_id, session, folder_name):
    try:
        # using .one() here may catch duplication bugs
        return session.query(UIDValidity).filter_by(
            imapaccount_id=account_id, folder_name=folder_name).one()
    except NoResultFound:
        return None


def uidvalidity_valid(account_id, session, selected_uidvalidity, folder_name,
                      cached_uidvalidity=None):
    """ Validate UIDVALIDITY on currently selected folder. """
    if cached_uidvalidity is None:
        cached_uidvalidity = get_uidvalidity(account_id,
                                             session, folder_name).uid_validity
        assert type(cached_uidvalidity) == type(selected_uidvalidity), \
            "cached_validity: {0} / selected_uidvalidity: {1}".format(
                type(cached_uidvalidity),
                type(selected_uidvalidity))

    if cached_uidvalidity is None:
        # no row is basically equivalent to UIDVALIDITY == -inf
        return True
    else:
        return selected_uidvalidity >= cached_uidvalidity


def update_uidvalidity(account_id, session, folder_name, uidvalidity,
                       highestmodseq):
    cached_validity = get_uidvalidity(account_id, session, folder_name)
    if cached_validity is None:
        cached_validity = UIDValidity(imapaccount_id=account_id,
                                      folder_name=folder_name)
    cached_validity.highestmodseq = highestmodseq
    cached_validity.uid_validity = uidvalidity
    session.add(cached_validity)


def create_imap_message(db_session, log, account, folder_name, msg):
    """ IMAP-specific message creation logic.

    This is the one function in this file that gets to take an account
    object instead of an account_id, because we need to relate the
    account to ImapUids for versioning to work, since it needs to look
    up the namespace.

    Returns
    -------
    imapuid : inbox.server.models.tables.imap.ImapUid
        New db object, which links to new Message and Block objects through
        relationships. All new objects are uncommitted.
    """
    new_msg = create_message(db_session, log, account, msg.uid, folder_name,
                             msg.internaldate, msg.flags, msg.body,
                             msg.created)

    if new_msg:
        imapuid = ImapUid(imapaccount=account, folder_name=folder_name,
                          msg_uid=msg.uid, message=new_msg)
        imapuid.update_imap_flags(msg.flags)

        new_msg.is_draft = imapuid.is_draft
        # NOTE: If we're going to make the Inbox datastore API support "read"
        # status, this is the place to add that data to Message, e.g.
        # new_msg.is_read = imapuid.is_seen.

        return imapuid


def add_gmail_attrs(db_session, log, new_uid, flags, folder_name, g_thrid,
                    g_msgid, g_labels, created):
    """ Gmail-specific post-create-message bits."""

    new_uid.message.g_msgid = g_msgid
    # NOTE: g_thrid == g_msgid on the first message in the thread :)
    new_uid.message.g_thrid = g_thrid
    new_uid.update_imap_flags(flags, g_labels)

    # NOTE: This code _requires_ autoflush=True, otherwise duplicate
    # threads may attempt to be created and crash.
    thread = new_uid.message.thread = ImapThread.from_gmail_message(
        db_session, new_uid.imapaccount.namespace, new_uid.message)
    # make sure this thread has all the correct labels
    existing_labels = {l.folder_name.lower() for l in thread.folders}
    # convert things like \Inbox -> Inbox, \Important -> Important
    # also, gmail labels are case-insensitive
    new_labels = {l.lstrip('\\').lower() for l in g_labels} | \
        {folder_name.lower()}
    # remove labels that have been deleted -- note that the \Sent label is
    # per-message, not per-thread, but since we always work at the thread
    # level, _we_ apply the label to the whole thread. same goes for
    # \Important.
    thread.folders = [l for l in thread.folders if l.folder_name in new_labels
                      or l.folder_name in ('sent', 'important')]
    # canonicalize "All Mail" to be "archive" in Inbox's data representation
    if new_uid.imapaccount.archive_folder_name:
        archive_folder_name = new_uid.imapaccount.archive_folder_name.lower()
        if archive_folder_name in new_labels:
            new_labels.remove(archive_folder_name)
            new_labels.add('archive')
    # add new labels
    for label in new_labels:
        if label not in existing_labels:
            item = FolderItem(thread=thread, folder_name=label)
            db_session.add(item)

    # Reconciliation for Sent Mail folder:
    if 'sent' in new_labels and not created and new_uid.message.inbox_uid:
        reconcile_message(db_session, log, new_uid.message.inbox_uid,
                          new_uid.message)

    return new_uid


def create_gmail_message(db_session, log, account, folder_name, msg):
    """ Gmail-specific message creation logic. """

    new_uid = create_imap_message(db_session, log, account, folder_name, msg)

    if new_uid:
        new_uid = add_gmail_attrs(db_session, log, new_uid, msg.flags,
                                  folder_name, msg.g_thrid, msg.g_msgid,
                                  msg.g_labels)

        # Execute new-message hooks. We call this here and not in
        # create_message() so that hooks have access to thread data.
        default_hook_manager.execute_hooks(account.id, new_uid.message)
        return new_uid
