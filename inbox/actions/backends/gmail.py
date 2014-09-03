""" Operations for syncing back local datastore changes to Gmail. """

from inbox.models.backends.imap import ImapThread
from inbox.actions.backends.imap import syncback_action

PROVIDER = 'gmail'

__all__ = ['set_remote_archived', 'set_remote_starred', 'set_remote_unread',
           'remote_save_draft', 'remote_delete_draft', 'remote_delete']


def uidvalidity_cb(db_session, account_id):
    """
    Gmail Syncback actions never ever touch the database and don't rely on
    local UIDs since they instead do SEARCHes based on X-GM-THRID to find
    the message UIDs to act on. So we don't actually need to care about
    UIDVALIDITY.

    """
    pass


def _archive(g_thrid, crispin_client):
    crispin_client.archive_thread(g_thrid)


def _get_g_thrid(namespace_id, thread_id, db_session):
    return db_session.query(ImapThread.g_thrid).filter_by(
        namespace_id=namespace_id,
        id=thread_id).one()[0]


def set_remote_archived(account, thread_id, archived, db_session):
    if not archived:
        # For now, implement unarchive as a move from all mail to inbox.
        return remote_move(account, thread_id, account.all_folder.name,
                           account.inbox_folder.name, db_session)

    def fn(account, db_session, crispin_client):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        _archive(g_thrid, crispin_client)

    inbox_folder = account.inbox_folder
    assert inbox_folder is not None
    inbox_folder_name = inbox_folder.name

    return syncback_action(fn, account, inbox_folder_name, db_session)


def set_remote_starred(account, thread_id, starred, db_session):
    def fn(account, db_session, crispin_client):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        crispin_client.set_starred(g_thrid, starred)

    return syncback_action(fn, account, account.all_folder.name, db_session)


def set_remote_unread(account, thread_id, unread, db_session):
    def fn(account, db_session, crispin_client):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        crispin_client.set_unread(g_thrid, unread)

    return syncback_action(fn, account, account.all_folder.name, db_session)


def remote_move(account, thread_id, from_folder_name, to_folder_name,
                db_session):
    if from_folder_name == to_folder_name:
        return

    def fn(account, db_session, crispin_client):
        inbox_folder_name = crispin_client.folder_names()['inbox']
        all_folder_name = crispin_client.folder_names()['all']
        if from_folder_name == inbox_folder_name:
            if to_folder_name == all_folder_name:
                return _archive(thread_id, crispin_client)
            else:
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                                       db_session)
                _archive(g_thrid, crispin_client)
                crispin_client.add_label(g_thrid, to_folder_name)
        elif from_folder_name in crispin_client.folder_names()['labels']:
            if to_folder_name in crispin_client.folder_names()['labels']:
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                                       db_session)
                crispin_client.add_label(g_thrid, to_folder_name)
            elif to_folder_name == inbox_folder_name:
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                                       db_session)
                crispin_client.copy_thread(g_thrid, to_folder_name)
            elif to_folder_name != all_folder_name:
                raise Exception("Should never get here! to_folder_name: {}"
                                .format(to_folder_name))
            crispin_client.select_folder(crispin_client.folder_names()['all'],
                                         uidvalidity_cb)
            crispin_client.remove_label(g_thrid, from_folder_name)
            # do nothing if moving to all mail
        elif from_folder_name == all_folder_name:
            g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
            if to_folder_name in crispin_client.folder_names()['labels']:
                crispin_client.add_label(g_thrid, to_folder_name)
            elif to_folder_name == inbox_folder_name:
                crispin_client.copy_thread(g_thrid, to_folder_name)
            else:
                raise Exception("Should never get here! to_folder_name: {}"
                                .format(to_folder_name))
        else:
            raise Exception("Unknown from_folder_name '{}'".
                            format(from_folder_name))

    return syncback_action(fn, account, from_folder_name, db_session)


def _remote_copy(account, thread_id, from_folder, to_folder, db_session):
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

    return syncback_action(fn, account, from_folder, db_session)


def remote_delete(account, thread_id, folder_name, db_session):
    def fn(account, db_session, crispin_client):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)

        inbox_folder = crispin_client.folder_names()['inbox']
        all_folder = crispin_client.folder_names()['all']
        drafts_folder = crispin_client.folder_names()['drafts']

        # Move to All Mail
        if folder_name == inbox_folder:
            return _archive(g_thrid, crispin_client)
        # Remove \Draft, move to Trash
        elif folder_name == drafts_folder:
            crispin_client.select_folder(
                crispin_client.folder_names()['all'], uidvalidity_cb)
            crispin_client.delete(g_thrid, folder_name)
        # Remove label, keep in All Mail
        elif folder_name in crispin_client.folder_names()['labels']:
            crispin_client.select_folder(
                crispin_client.folder_names()['all'], uidvalidity_cb)
            crispin_client.remove_label(g_thrid, folder_name)
        # Move to Trash
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

    return syncback_action(fn, account, folder_name, db_session)


def remote_save_draft(account, folder_name, message, db_session, date=None):
    def fn(account, db_session, crispin_client):
        assert folder_name == crispin_client.folder_names()['drafts']
        crispin_client.save_draft(message, date)

    return syncback_action(fn, account, folder_name, db_session)


def remote_delete_draft(account, folder_name, inbox_uid, db_session):
    def fn(account, db_session, crispin_client):
        assert folder_name == crispin_client.folder_names()['drafts']
        crispin_client.delete_draft(inbox_uid)

    return syncback_action(fn, account, folder_name, db_session)
