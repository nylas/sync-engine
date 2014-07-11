""" Operations for syncing back local datastore changes to Gmail.

For IMAP, we could guarantee correctness with a full bidirectional sync by
using a conservative algorithm like OfflineIMAP's
(http://offlineimap.org/howitworks.html), but doing so wouldn't take advantage
of newer IMAP extensions like CONDSTORE that make us have to do much less
comparison and bookkeeping work.

We don't get any notion of "transactions" from the remote with IMAP. Here are
the possible cases for IMAP message changes:

* new
  - This message is either new-new and needs to be synced to us, or it's a
    "sent" or "draft" message and we need to check whether or not we have it,
    since we may have already saved a local copy. If we do already have it,
    we need to make a new ImapUid for it and associate the Message object with
    its ImapUid.
* changed
  - Update our flags or do nothing if the message isn't present locally. (NOTE:
    this could mean the message has been moved locally, in which case we will
    LOSE the flag change. We can fix this case in an eventually consistent
    manner by sanchecking flags on all messages in an account once a day or
    so.)
* delete
  - We always figure this out by comparing message lists against the local
    repo. Since we're using the mailsync-specific ImapUid objects for
    comparison, we automatically exclude Inbox-local sent and draft messages
    from this calculation.

We don't currently handle these operations on the special folders 'junk',
'trash', 'sent', 'flagged'.
"""
from inbox.crispin import writable_connection_pool

from inbox.models.backends.imap import ImapThread

PROVIDER = 'gmail'


class ActionError(Exception):
    pass


def uidvalidity_cb(db_session, account_id):
    """ Gmail Syncback actions never ever touch the database and don't rely on
        local UIDs since they instead do SEARCHes based on X-GM-THRID to find
        the message UIDs to act on. So we don't actually need to care about
        UIDVALIDITY.
    """
    pass


def _syncback_action(fn, account, folder_name, db_session):
    """ `folder_name` is a Gmail folder name. """
    assert folder_name, "folder '{}' is not selectable".format(folder_name)

    with writable_connection_pool(account.id).get() as crispin_client:
        crispin_client.select_folder(folder_name, uidvalidity_cb)
        fn(account, db_session, crispin_client)


def _archive(g_thrid, crispin_client):
    crispin_client.archive_thread(g_thrid)


def _get_g_thrid(namespace_id, thread_id, db_session):
    return db_session.query(ImapThread.g_thrid).filter_by(
        namespace_id=namespace_id,
        id=thread_id).one()[0]


def set_remote_archived(account, thread_id, archived, db_session):
    if not archived:
        # For now, implement unarchive as a move from all mail to inbox.
        return remote_move(account, thread_id, account.all_folder,
                           account.inbox_folder, db_session)

    def fn(account, db_session, crispin_client):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        _archive(g_thrid, crispin_client)

    inbox_folder = account.inbox_folder
    assert inbox_folder is not None
    inbox_folder_name = inbox_folder.name

    return _syncback_action(fn, account, inbox_folder_name, db_session)


def set_remote_starred(account, thread_id, starred, db_session):
    def fn(account, db_session, crispin_client):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        crispin_client.set_starred(g_thrid, starred)

    return _syncback_action(fn, account, account.all_folder.name, db_session)


def set_remote_unread(account, thread_id, unread, db_session):
    def fn(account, db_session, crispin_client):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        crispin_client.set_unread(g_thrid, unread)

    return _syncback_action(fn, account, account.all_folder.name, db_session)


def remote_move(account, thread_id, from_folder, to_folder, db_session):
    """ NOTE: We are not planning to use this function yet since Inbox never
        modifies Gmail IMAP labels.
    """
    if from_folder == to_folder:
        return

    def fn(account, db_session, crispin_client):
        inbox_folder = crispin_client.folder_names()['inbox']
        all_folder = crispin_client.folder_names()['all']
        if from_folder == inbox_folder:
            if to_folder == all_folder:
                return _archive(thread_id, crispin_client)
            else:
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                                       db_session)
                _archive(g_thrid, crispin_client)
                crispin_client.add_label(g_thrid, to_folder)
        elif from_folder in crispin_client.folder_names()['labels']:
            if to_folder in crispin_client.folder_names()['labels']:
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                                       db_session)
                crispin_client.add_label(g_thrid, to_folder)
            elif to_folder == inbox_folder:
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                                       db_session)
                crispin_client.copy_thread(g_thrid, to_folder)
            elif to_folder != all_folder:
                raise Exception("Should never get here! to_folder: {}"
                                .format(to_folder))
            crispin_client.select_folder(crispin_client.folder_names()['all'],
                                         uidvalidity_cb)
            crispin_client.remove_label(g_thrid, from_folder)
            # do nothing if moving to all mail
        elif from_folder == all_folder:
            g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
            if to_folder in crispin_client.folder_names()['labels']:
                crispin_client.add_label(g_thrid, to_folder)
            elif to_folder == inbox_folder:
                crispin_client.copy_thread(g_thrid, to_folder)
            else:
                raise Exception("Should never get here! to_folder: {}"
                                .format(to_folder))
        else:
            raise Exception("Unknown from_folder '{}'".format(from_folder))

    return _syncback_action(fn, account, from_folder, db_session)


def remote_copy(account, thread_id, from_folder, to_folder, db_session):
    """ NOTE: We are not planning to use this function yet since Inbox never
        modifies Gmail IMAP labels.
    """
    if from_folder == to_folder:
        return

    def fn(account, db_session, crispin_client):
        inbox_folder = crispin_client.folder_names()['inbox']
        all_folder = crispin_client.folder_names()['all']
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        if to_folder == inbox_folder:
            crispin_client.copy_thread(g_thrid, to_folder)
        elif to_folder != all_folder:
            crispin_client.add_label(g_thrid, to_folder)
        # copy a thread to all mail is a noop

    return _syncback_action(fn, account, from_folder, db_session)


def remote_delete(account, thread_id, folder_name, db_session):
    def fn(account, db_session, crispin_client):
        inbox_folder = crispin_client.folder_names()['inbox']
        all_folder = crispin_client.folder_names()['all']
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        if folder_name == inbox_folder:
            return _archive(g_thrid, crispin_client)
        elif folder_name in crispin_client.folder_names()['labels']:
            crispin_client.select_folder(
                crispin_client.folder_names()['all'], uidvalidity_cb)
            crispin_client.remove_label(g_thrid, folder_name)
        elif folder_name == all_folder:
            # delete thread from all mail: really delete it (move it to trash
            # where it will be permanently deleted after 30 days, see
            # https://support.google.com/mail/answer/78755?hl=en)
            # XXX: does copy() work here, or do we have to actually _move_
            # the message? do we also need to delete it from all labels and
            # stuff? not sure how this works really.
            crispin_client.copy_thread(
                g_thrid, crispin_client.folder_names()['trash'])
        else:
            raise Exception("Unknown folder_name '{0}'".format(folder_name))

    return _syncback_action(fn, account, folder_name, db_session)


def remote_save_draft(account, folder_name, message, db_session, date=None):
    def fn(account, db_session, crispin_client):
        assert folder_name == crispin_client.folder_names()['drafts']
        crispin_client.save_draft(message, date)

    return _syncback_action(fn, account, folder_name, db_session)


def remote_delete_draft(account, folder_name, inbox_uid, db_session):
    def fn(account, db_session, crispin_client):
        assert folder_name == crispin_client.folder_names()['drafts']
        crispin_client.delete_draft(inbox_uid)

    return _syncback_action(fn, account, folder_name, db_session)
