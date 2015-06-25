import platform
from inbox.mailsync.service import SyncService
from inbox.models import Account


def purge_other_accounts(db, default_account):
    db.session.query(Account).filter(
        Account.id != default_account.id).delete(synchronize_session='fetch')
    db.session.commit()


def test_start_already_assigned_accounts(db, default_account):
    purge_other_accounts(db, default_account)
    default_account.sync_host = platform.node()
    ss = SyncService(cpu_id=default_account.id % 2, total_cpus=2)
    assert ss.accounts_to_start() == [default_account.id]


def test_dont_start_accounts_for_other_cpus(db, default_account):
    purge_other_accounts(db, default_account)
    default_account.sync_host = platform.node()
    ss = SyncService(cpu_id=default_account.id + 1, total_cpus=2**22)
    assert ss.accounts_to_start() == []


def test_dont_start_accounts_on_other_host(db, default_account):
    purge_other_accounts(db, default_account)
    default_account.sync_host = 'other-host'
    db.session.commit()
    ss = SyncService(cpu_id=1, total_cpus=2)
    assert ss.accounts_to_start() == []


def test_start_new_accounts_when_stealing_enabled(db, default_account):
    purge_other_accounts(db, default_account)
    default_account.sync_host = None
    db.session.commit()
    ss = SyncService(cpu_id=default_account.id % 2, total_cpus=2)
    assert ss.accounts_to_start() == [default_account.id]
    db.session.expire_all()
    assert default_account.sync_host == platform.node()


def test_dont_start_new_accounts_when_stealing_disabled(db, config,
                                                        default_account):
    purge_other_accounts(db, default_account)
    default_account.sync_host = None
    db.session.commit()
    config['SYNC_STEAL_ACCOUNTS'] = False
    ss = SyncService(cpu_id=default_account.id % 2, total_cpus=2)
    assert ss.accounts_to_start() == []
    assert default_account.sync_host is None


def test_dont_start_disabled_accounts(db, config, default_account):
    purge_other_accounts(db, default_account)
    config['SYNC_STEAL_ACCOUNTS'] = True
    default_account.sync_host = None
    default_account.disable_sync()
    db.session.commit()
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss.accounts_to_start() == []
    assert default_account.sync_host is None
    assert default_account.sync_should_run is False

    default_account.sync_host = platform.node()
    default_account.disable_sync()
    db.session.commit()
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss.accounts_to_start() == []
    assert default_account.sync_should_run is False

    # Invalid Credentials
    default_account.mark_invalid()
    default_account.sync_host = None
    db.session.commit()

    # Don't steal invalid accounts
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss.accounts_to_start() == []

    # Don't explicitly start invalid accounts
    default_account.sync_host = platform.node()
    db.session.commit()
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss.accounts_to_start() == []


def test_concurrent_syncs(db, default_account, config):
    purge_other_accounts(db, default_account)
    ss1 = SyncService(cpu_id=default_account.id % 2, total_cpus=2)
    ss2 = SyncService(cpu_id=default_account.id % 2, total_cpus=2)
    ss2.host = 'other-host'
    # Check that only one SyncService instance claims the account.
    assert ss1.accounts_to_start() == [default_account.id]
    assert ss2.accounts_to_start() == []


def test_sync_transitions(db, default_account, config):
    purge_other_accounts(db, default_account)
    ss = SyncService(cpu_id=default_account.id % 2, total_cpus=2)
    default_account.enable_sync()
    db.session.commit()
    assert ss.accounts_to_start() == [default_account.id]

    default_account.disable_sync('manual')
    db.session.commit()
    assert ss.accounts_to_start() == []
    assert default_account.sync_should_run is False
    assert default_account._sync_status['sync_disabled_reason'] == 'manual'

    default_account.mark_invalid()
    db.session.commit()
    assert ss.accounts_to_start() == []
    assert default_account.sync_state == 'invalid'
    assert default_account._sync_status['sync_disabled_reason'] == \
        'invalid credentials'
    assert default_account.sync_should_run is False
