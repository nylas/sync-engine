import pytest
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


@pytest.mark.parametrize('db_zone', ['us-west-2a', 'us-west-2b'])
@pytest.mark.parametrize('steal', [True, False])
def test_stealing_limited_by_zone_and_stealing_configuration(
        db, config, default_account, db_zone, steal):
    host = platform.node()
    host_zone = 'us-west-2a'

    config['DATABASE_HOSTS'][0]['ZONE'] = db_zone
    config['ZONE'] = host_zone
    config['SYNC_STEAL_ACCOUNTS'] = steal
    purge_other_accounts(default_account)
    default_account.sync_host = None
    db.session.commit()
    process_identifier = '{}:{}'.format(host, 0)
    ss = SyncService(process_identifier=process_identifier, cpu_id=0)
    if steal and host_zone == db_zone:
        assert ss.accounts_to_start() == {default_account.id}
    else:
        assert ss.accounts_to_start() == set()


def test_stealing_if_zones_not_configured(db, config, default_account):
    config['SYNC_STEAL_ACCOUNTS'] = True
    if 'ZONE' in config:
        del config['ZONE']
    purge_other_accounts(default_account)
    default_account.sync_host = None
    db.session.commit()
    process_identifier = '{}:{}'.format(host, 0)
    ss = SyncService(process_identifier=process_identifier, cpu_id=0)
    assert ss.accounts_to_start() == {default_account.id}
