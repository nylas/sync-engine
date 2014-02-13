from ..util.crispin import crispin_client

ACCOUNT_ID=1
NAMESPACE_ID=1
THREAD_ID=1

# Unit tests for the functions, not the queue runners. These tests use a real
# Gmail test account and idempotently put the account back to the state it
# started in when the test is done. They intentionally make the local Inbox
# datastore out of sync. That's okay---our goal is to minimally unit test the
# syncback methods, not to do a system-level test here.

def test_archive_move_syncback(db, config):
    from inbox.server.actions.gmail import archive, move, uidvalidity_cb
    from inbox.server.models.tables import Thread, ImapAccount

    archive(ACCOUNT_ID, THREAD_ID)

    g_thrid = db.session.query(Thread.g_thrid).filter_by(
            id=THREAD_ID, namespace_id=NAMESPACE_ID).one()[0]
    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    client = crispin_client(account.id, account.provider)
    with client.pool.get() as c:
        client.select_folder(account.inbox_folder_name, uidvalidity_cb, c)
        inbox_uids = client.find_messages(g_thrid, c)
        assert not inbox_uids, "thread still present in inbox"
        client.select_folder(account.archive_folder_name, uidvalidity_cb, c)
        archive_uids = client.find_messages(g_thrid, c)
        assert archive_uids, "thread missing from archive"

    # and put things back the way they were :)
    move(ACCOUNT_ID, THREAD_ID, 'archive', 'inbox')
    with client.pool.get() as c:
        client.select_folder(account.inbox_folder_name, uidvalidity_cb, c)
        inbox_uids = client.find_messages(g_thrid, c)
        assert inbox_uids, "thread missing from inbox"
        client.select_folder(account.archive_folder_name, uidvalidity_cb, c)
        archive_uids = client.find_messages(g_thrid, c)
        assert archive_uids, "thread missing from archive"

def test_copy_delete_syncback(db, config):
    from inbox.server.actions.gmail import copy, delete, uidvalidity_cb
    from inbox.server.models.tables import Thread, ImapAccount, Namespace

    copy(ACCOUNT_ID, THREAD_ID, 'inbox', 'testlabel')

    g_thrid = db.session.query(Thread.g_thrid).filter_by(
            id=THREAD_ID, namespace_id=NAMESPACE_ID).one()[0]
    account = db.session.query(ImapAccount).join(Namespace) \
            .filter_by(id=ACCOUNT_ID).one()
    client = crispin_client(account.id, account.provider)
    with client.pool.get() as c:
        client.select_folder(account.inbox_folder_name, uidvalidity_cb, c)
        inbox_uids = client.find_messages(g_thrid, c)
        assert inbox_uids, "thread missing from inbox"
        client.select_folder(account.archive_folder_name, uidvalidity_cb, c)
        archive_uids = client.find_messages(g_thrid, c)
        assert archive_uids, "thread missing from archive"
        client.select_folder('testlabel', uidvalidity_cb, c)
        testlabel_uids = client.find_messages(g_thrid, c)
        assert testlabel_uids, "thread missing from testlabel"

    # and put things back the way they were :)
    delete(ACCOUNT_ID, THREAD_ID, 'testlabel')
    with client.pool.get() as c:
        client.select_folder(account.inbox_folder_name, uidvalidity_cb, c)
        inbox_uids = client.find_messages(g_thrid, c)
        assert inbox_uids, "thread missing from inbox"
        client.select_folder(account.archive_folder_name, uidvalidity_cb, c)
        archive_uids = client.find_messages(g_thrid, c)
        assert archive_uids, "thread missing from archive"
        client.select_folder('testlabel', uidvalidity_cb, c)
        testlabel_uids = client.find_messages(g_thrid, c)
        assert not testlabel_uids, "thread still present in testlabel"
