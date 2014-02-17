"""
Operations for syncing back local datastore changes to Gmail.

ACTIONS MUST BE IDEMPOTENT! We are going to have task workers guarantee
at-least-once semantics.

Syncback actions don't update anything in the local datastore; the inbox
datastore is updated asynchronously (see namespace.py) and bookkeeping about
the backend state is updated when the changes show up in the mail sync engine.
That way our notion of the backend state is actually reflected by our recorded
HIGHESTMODSEQ.

We don't currently handle these operations on the special folders 'junk',
'trash', 'sent', 'flagged'.
"""
from ..crispin import new_crispin

from ..models import session_scope
from ..models.tables import ImapAccount, Namespace, Thread

class ActionError(Exception): pass

def uidvalidity_cb(db_session, account_id):
    """ Gmail Syncback actions never ever touch the database and don't rely on
        local UIDs since they instead do SEARCHes based on X-GM-THRID to find
        the message UIDs to act on. So we don't actually need to care about
        UIDVALIDITY.
    """
    pass

def _translate_folder_name(inbox_folder_name, crispin_client, c):
    """
    Folder names are *Inbox* datastore folder names; it's the responsibility
    of syncback API functions to translate that back to the proper Gmail folder
    name.
    """
    if inbox_folder_name in crispin_client.folder_names(c)['labels']:
        return inbox_folder_name
    elif inbox_folder_name in crispin_client.folder_names(c):
        return crispin_client.folder_names(c)[inbox_folder_name]
    else:
        raise Exception("weird Gmail folder that's not special or a label: {0}".format(inbox_folder_name))

def _syncback_action(fn, imapaccount_id, folder_name):
    """ `folder_name` is an Inbox folder name, not a Gmail folder name. """
    with session_scope() as db_session:
        account = db_session.query(ImapAccount).join(Namespace).filter_by(
                id=imapaccount_id).one()
        crispin_client = new_crispin(account.id, account.provider,
                conn_pool_size=1)
        with crispin_client.pool.get() as c:
            crispin_client.select_folder(
                    _translate_folder_name(folder_name, crispin_client, c),
                    uidvalidity_cb, c)
            fn(account, db_session, crispin_client, c)

def _archive(g_thrid, crispin_client, c):
    assert crispin_client.selected_folder_name \
            == crispin_client.folder_names(c)['inbox'], "must select inbox first"
    crispin_client.archive_thread(g_thrid, c)

def _get_g_thrid(namespace_id, thread_id, db_session):
    return db_session.query(Thread.g_thrid).filter_by(
            namespace_id=namespace_id,
            id=thread_id).one()[0]

def archive(imapaccount_id, thread_id):
    def fn(account, db_session, crispin_client, c):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        return _archive(g_thrid, crispin_client, c)

    return _syncback_action(fn, imapaccount_id, 'inbox')

def move(imapaccount_id, thread_id, from_folder, to_folder):
    if from_folder == to_folder:
        return

    def fn(account, db_session, crispin_client, c):
        if from_folder == 'inbox':
            if to_folder == 'archive':
                return _archive(thread_id, crispin_client, c)
            else:
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                        db_session)
                _archive(g_thrid, crispin_client, c)
                crispin_client.add_label(g_thrid,
                        _translate_folder_name(to_folder, crispin_client, c), c)
        elif from_folder in crispin_client.folder_names(c)['labels']:
            if to_folder in crispin_client.folder_names(c)['labels']:
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                        db_session)
                crispin_client.add_label(g_thrid,
                        _translate_folder_name(to_folder, crispin_client, c),
                        c)
                crispin_client.select_folder(
                        crispin_client.folder_names(c)['all'],
                        uidvalidity_cb, c)
                crispin_client.remove_label(g_thrid,
                        _translate_folder_name(from_folder, crispin_client, c),
                        c)
            elif to_folder == 'inbox':
                g_thrid = _get_g_thrid(account.namespace.id, thread_id,
                        db_session)
                crispin_client.copy_thread(g_thrid,
                        _translate_folder_name(to_folder, crispin_client, c),
                        c)
            elif to_folder != 'archive':
                raise Exception("Should never get here! to_folder: {0}" \
                        .format(to_folder))
            # do nothing if moving to all mail
        elif from_folder == 'archive':
            g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
            if to_folder in crispin_client.folder_names(c)['labels']:
                crispin_client.add_label(g_thrid,
                        _translate_folder_name(to_folder, crispin_client, c),
                        c)
            elif to_folder == 'inbox':
                crispin_client.copy_thread(g_thrid,
                        _translate_folder_name(to_folder, crispin_client, c),
                        c)
            else:
                raise Exception("Should never get here! to_folder: {0}".format(to_folder))
        else:
            raise Exception("Unknown from_folder '{0}'".format(from_folder))

    return _syncback_action(fn, imapaccount_id, from_folder)

def copy(imapaccount_id, thread_id, from_folder, to_folder):
    if from_folder == to_folder:
        return

    def fn(account, db_session, crispin_client, c):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        if to_folder == 'inbox':
            crispin_client.copy_thread(g_thrid,
                    _translate_folder_name(to_folder, crispin_client, c), c)
        elif to_folder != 'archive':
            crispin_client.add_label(g_thrid,
                    _translate_folder_name(to_folder, crispin_client, c), c)
        # copy a thread to all mail is a noop

    return _syncback_action(fn, imapaccount_id, from_folder)

def delete(imapaccount_id, thread_id, folder_name):
    def fn(account, db_session, crispin_client, c):
        g_thrid = _get_g_thrid(account.namespace.id, thread_id, db_session)
        if folder_name == 'inbox':
            return _archive(g_thrid, crispin_client, c)
        elif folder_name in crispin_client.folder_names(c)['labels']:
            crispin_client.select_folder(
                    crispin_client.folder_names(c)['all'], uidvalidity_cb, c)
            crispin_client.remove_label(g_thrid,
                    _translate_folder_name(folder_name, crispin_client, c), c)
        elif folder_name == 'archive':
            # delete thread from all mail: really delete it (move it to trash
            # where it will be permanently deleted after 30 days, see
            # https://support.google.com/mail/answer/78755?hl=en)
            # XXX: does copy() work here, or do we have to actually _move_
            # the message? do we also need to delete it from all labels and
            # stuff? not sure how this works really.
            crispin_client.copy_thread(g_thrid,
                    crispin_client.folder_names(c)['trash'], c)
        else:
            raise Exception("Unknown folder_name '{0}'".format(folder_name))

    return _syncback_action(fn, imapaccount_id, folder_name)
