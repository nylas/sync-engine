import platform
from inbox.ignition import engine_manager
from inbox.mailsync.service import SyncService
from inbox.models import Account, Namespace
from inbox.models.session import session_scope_by_shard_id, session_scope


host = platform.node()


def purge_other_accounts(default_account=None):
    for key in engine_manager.engines:
        with session_scope_by_shard_id(key) as db_session:
            q = db_session.query(Account)
            if default_account is not None:
                q = q.filter(Account.id != default_account.id)
            q.delete(synchronize_session='fetch')
            db_session.commit()


def test_start_already_assigned_accounts(db, default_account):
    purge_other_accounts(default_account)
    process_identifier = '{}:{}'.format(host, default_account.id % 2)
    default_account.sync_host = process_identifier
    db.session.commit()
    ss = SyncService(process_identifier=process_identifier,
                     cpu_id=default_account.id % 2)
    assert ss.accounts_to_start() == {default_account.id}


def test_dont_start_accounts_on_other_host(db, default_account):
    purge_other_accounts(default_account)
    default_account.sync_host = 'other-host'
    db.session.commit()
    ss = SyncService(
        process_identifier='{}:{}'.format(host, 1),
        cpu_id=1)
    assert ss.accounts_to_start() == set()


def test_start_new_accounts_when_stealing_enabled(db, default_account):
    purge_other_accounts(default_account)
    default_account.sync_host = None
    db.session.commit()
    process_identifier = '{}:{}'.format(host, default_account.id % 2)
    ss = SyncService(
        process_identifier=process_identifier,
        cpu_id=default_account.id % 2)
    assert ss.accounts_to_start() == {default_account.id}
    db.session.expire_all()
    assert default_account.sync_host == process_identifier


def test_dont_start_new_accounts_when_stealing_disabled(db, config,
                                                        default_account):
    purge_other_accounts(default_account)
    default_account.sync_host = None
    db.session.commit()
    config['SYNC_STEAL_ACCOUNTS'] = False
    ss = SyncService(
        process_identifier='{}:{}'.format(host, default_account.id % 2),
        cpu_id=default_account.id % 2)
    assert ss.accounts_to_start() == set()
    assert default_account.sync_host is None


def test_dont_start_disabled_accounts(db, config, default_account):
    purge_other_accounts(default_account)
    config['SYNC_STEAL_ACCOUNTS'] = True
    default_account.sync_host = None
    default_account.disable_sync(reason='testing')
    db.session.commit()
    ss = SyncService(
        process_identifier='{}:{}'.format(host, 0),
        cpu_id=0)
    assert ss.accounts_to_start() == set()
    assert default_account.sync_host is None
    assert default_account.sync_should_run is False

    default_account.sync_host = platform.node()
    default_account.disable_sync('testing')
    db.session.commit()
    ss = SyncService(
        process_identifier='{}:{}'.format(host, 0),
        cpu_id=0)
    assert ss.accounts_to_start() == set()
    assert default_account.sync_should_run is False

    # Invalid Credentials
    default_account.mark_invalid()
    default_account.sync_host = None
    db.session.commit()

    # Don't steal invalid accounts
    ss = SyncService(
        process_identifier='{}:{}'.format(host, 0),
        cpu_id=0)
    assert ss.accounts_to_start() == set()

    # Don't explicitly start invalid accounts
    default_account.sync_host = platform.node()
    db.session.commit()
    ss = SyncService(
        process_identifier='{}:{}'.format(host, 0),
        cpu_id=0)
    assert ss.accounts_to_start() == set()


def test_concurrent_syncs(db, default_account, config):
    purge_other_accounts(default_account)
    default_account.sync_host = None
    db.session.commit()
    ss1 = SyncService(
        process_identifier='{}:{}'.format(host, default_account.id % 2),
        cpu_id=default_account.id % 2)
    ss2 = SyncService(
        process_identifier='{}:{}'.format('otherhost', default_account.id % 2),
        cpu_id=default_account.id % 2)
    # Check that only one SyncService instance claims the account.
    assert ss1.accounts_to_start() == {default_account.id}
    assert ss2.accounts_to_start() == set()


def test_sync_transitions(db, default_account, config):
    default_account.sync_host = None
    db.session.commit()
    purge_other_accounts(default_account)
    ss = SyncService(
        process_identifier='{}:{}'.format(host, default_account.id % 2),
        cpu_id=default_account.id % 2)
    default_account.enable_sync()
    db.session.commit()
    assert ss.accounts_to_start() == {default_account.id}

    default_account.disable_sync('manual')
    db.session.commit()
    assert ss.accounts_to_start() == set()
    assert default_account.sync_should_run is False
    assert default_account._sync_status['sync_disabled_reason'] == 'manual'

    default_account.mark_invalid()
    db.session.commit()
    assert ss.accounts_to_start() == set()
    assert default_account.sync_state == 'invalid'
    assert default_account._sync_status['sync_disabled_reason'] == \
        'invalid credentials'
    assert default_account.sync_should_run is False


def test_accounts_started_on_all_shards(db, default_account, config):
    config['SYNC_STEAL_ACCOUNTS'] = True
    purge_other_accounts(default_account)
    default_account.sync_host = None
    db.session.commit()
    process_identifier = '{}:{}'.format(host, 0)
    ss = SyncService(
        process_identifier=process_identifier,
        cpu_id=0)
    account_ids = {default_account.id}
    for key in (0, 1):
        with session_scope_by_shard_id(key) as db_session:
            acc = Account()
            acc.namespace = Namespace()
            db_session.add(acc)
            db_session.commit()
            account_ids.add(acc.id)

    assert len(account_ids) == 3
    assert set(ss.accounts_to_start()) == account_ids
    for id_ in account_ids:
        with session_scope(id_) as db_session:
            acc = db_session.query(Account).get(id_)
            assert acc.sync_host == process_identifier


def test_stealing_limited_by_host(db, config):
    host = platform.node()
    config['DATABASE_HOSTS'][0]['SHARDS'][0]['SYNC_HOSTS'] = [host]
    config['DATABASE_HOSTS'][0]['SHARDS'][1]['SYNC_HOSTS'] = ['otherhost']
    purge_other_accounts()
    process_identifier = '{}:{}'.format(host, 0)
    ss = SyncService(process_identifier=process_identifier, cpu_id=0)
    for key in (0, 1):
        with session_scope_by_shard_id(key) as db_session:
            acc = Account()
            acc.namespace = Namespace()
            db_session.add(acc)
            db_session.commit()

    ss.accounts_to_start()
    with session_scope_by_shard_id(0) as db_session:
        acc = db_session.query(Account).first()
        assert acc.sync_host == process_identifier
    with session_scope_by_shard_id(1) as db_session:
        acc = db_session.query(Account).first()
        assert acc.sync_host is None
