from tests.util.crispin import crispin_client

ACCOUNT_ID = 1
NAMESPACE_ID = 1
THREAD_ID = 2

# Unit tests for the functions, not the queue runners. These tests use a real
# Gmail test account and idempotently put the account back to the state it
# started in when the test is done. They intentionally make the local Inbox
# datastore out of sync. That's okay---our goal is to minimally unit test the
# syncback methods, not to do a system-level test here.


def test_archive_move_syncback(db, config):
    from inbox.actions.gmail import (set_remote_archived, remote_move,
                                     uidvalidity_cb)
    from inbox.models.backends.imap import ImapAccount, ImapThread
    g_thrid = db.session.query(ImapThread.g_thrid).filter_by(
        id=THREAD_ID, namespace_id=NAMESPACE_ID).one()[0]
    account = db.session.query(ImapAccount).get(ACCOUNT_ID)

    set_remote_archived(account, THREAD_ID, True, db.session)

    assert account.inbox_folder_id and account.all_folder_id, \
        "`inbox_folder_id` and `all_folder_id` cannot be NULL"
    with crispin_client(account.id, account.provider) as client:
        client.select_folder(account.inbox_folder.name, uidvalidity_cb)
        inbox_uids = client.find_messages(g_thrid)
        assert not inbox_uids, "thread still present in inbox"
        client.select_folder(account.all_folder.name, uidvalidity_cb)
        archive_uids = client.find_messages(g_thrid)
        assert archive_uids, "thread missing from archive"

        # and put things back the way they were :)
        remote_move(account, THREAD_ID, account.all_folder.name,
                    account.inbox_folder.name, db.session)
        client.select_folder(account.inbox_folder.name, uidvalidity_cb)
        inbox_uids = client.find_messages(g_thrid)
        assert inbox_uids, "thread missing from inbox"
        client.select_folder(account.all_folder.name, uidvalidity_cb)
        archive_uids = client.find_messages(g_thrid)
        assert archive_uids, "thread missing from archive"


def test_copy_delete_syncback(db, config):
    from inbox.actions.gmail import (remote_copy, remote_delete,
                                     uidvalidity_cb)
    from inbox.models.backends.imap import ImapAccount, ImapThread

    g_thrid = db.session.query(ImapThread.g_thrid). \
        filter_by(id=THREAD_ID, namespace_id=NAMESPACE_ID).one()[0]
    account = db.session.query(ImapAccount).get(ACCOUNT_ID)

    remote_copy(account, THREAD_ID, account.inbox_folder.name, 'testlabel',
                db.session)

    with crispin_client(account.id, account.provider) as client:
        client.select_folder(account.inbox_folder.name, uidvalidity_cb)
        inbox_uids = client.find_messages(g_thrid)
        assert inbox_uids, "thread missing from inbox"
        client.select_folder(account.all_folder.name, uidvalidity_cb)
        archive_uids = client.find_messages(g_thrid)
        assert archive_uids, "thread missing from archive"
        client.select_folder('testlabel', uidvalidity_cb)
        testlabel_uids = client.find_messages(g_thrid)
        assert testlabel_uids, "thread missing from testlabel"

        # and put things back the way they were :)
        remote_delete(account, THREAD_ID, 'testlabel', db.session)
        client.select_folder(account.inbox_folder.name, uidvalidity_cb)
        inbox_uids = client.find_messages(g_thrid)
        assert inbox_uids, "thread missing from inbox"
        client.select_folder(account.all_folder.name, uidvalidity_cb)
        archive_uids = client.find_messages(g_thrid)
        assert archive_uids, "thread missing from archive"
        client.select_folder('testlabel', uidvalidity_cb)
        testlabel_uids = client.find_messages(g_thrid)
        assert not testlabel_uids, "thread still present in testlabel"


def test_remote_unread_syncback(db, config):
    from inbox.actions.gmail import set_remote_unread, uidvalidity_cb
    from inbox.models.backends.imap import ImapAccount, ImapThread

    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    g_thrid, = db.session.query(ImapThread.g_thrid). \
        filter_by(id=THREAD_ID).one()

    set_remote_unread(account, THREAD_ID, True, db.session)

    with crispin_client(account.id, account.provider) as client:
        client.select_folder(account.all_folder.name, uidvalidity_cb)
        uids = client.find_messages(g_thrid)
        assert not any('\\Seen' in flags for flags, _ in
                       client.flags(uids).values())

        set_remote_unread(account, THREAD_ID, False, db.session)
        assert all('\\Seen' in flags for flags, _ in
                   client.flags(uids).values())

        set_remote_unread(account, THREAD_ID, True, db.session)
        assert not any('\\Seen' in flags for flags, _ in
                       client.flags(uids).values())


# TODO: Test more of the different cases here.

# Higher-level tests.


def test_queue_running(db):
    """ Just the very minimal basics for now: makes sure that the methods run
        without raising an exception. You can use rq-dashboard and a Gmail
        browser window to look in more depth. We'll want to add some
        automatic verification of the behaviour here eventually (see the
        previous tests), but for now I'm leaving it lean and fast.
    """
    from inbox.actions import archive, rqworker

    archive(ACCOUNT_ID, 8)
    # process actions queue
    rqworker(burst=True)

    # TODO: Test more of the different cases here.
