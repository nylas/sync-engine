import platform
from inbox.mailsync.service import SyncService
from tests.util.base import default_account
__all__ = ['default_account']


def test_sync_start(db, default_account, config):

    # Make sure having fqdn set locally gets assigned to us
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss._get_local_accounts() == [1]

    # Not from other cpus
    ss = SyncService(cpu_id=1, total_cpus=1)
    assert ss._get_local_accounts() == []

    # Different host
    default_account.sync_host = "some-random-host"
    db.session.commit()
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss._get_local_accounts() == []

    # Explicit
    default_account.sync_host = platform.node()
    db.session.commit()
    assert ss._get_local_accounts() == [1]

    default_account.sync_host = None
    db.session.commit()

    # No host, work stealing enabled
    config['SYNC_STEAL_ACCOUNTS'] = True
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss._get_local_accounts() == [1]

    # No host, no work stealing disabled
    config['SYNC_STEAL_ACCOUNTS'] = False
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss._get_local_accounts() == []

    default_account.disable_sync()
    default_account.sync_host = None
    db.session.commit()

    # Don't steal disabled accounts
    config['SYNC_STEAL_ACCOUNTS'] = True
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss._get_local_accounts() == []

    # Don't explicitly start disabled accounts
    default_account.sync_host = platform.node()
    db.session.commit()
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss._get_local_accounts() == []

    # Invalid Credentials
    default_account.mark_invalid()
    default_account.sync_host = None
    db.session.commit()

    # Don't steal invalid accounts
    config['SYNC_STEAL_ACCOUNTS'] = True
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss._get_local_accounts() == []

    # Don't explicitly start invalid accounts
    default_account.sync_host = platform.node()
    db.session.commit()
    ss = SyncService(cpu_id=0, total_cpus=1)
    assert ss._get_local_accounts() == []


def test_sync_transitions(db, default_account, config):
    ss = SyncService(cpu_id=0, total_cpus=1)
    default_account.enable_sync()
    db.session.commit()
    assert ss._get_local_accounts() == [1]

    default_account.disable_sync('manual')
    db.session.commit()
    assert ss._get_local_accounts() == []
    assert default_account._sync_status['sync_disabled_reason'] == 'manual'

    default_account.mark_invalid()
    db.session.commit()
    assert ss._get_local_accounts() == []
    assert default_account.sync_state == 'invalid'
    assert default_account._sync_status['sync_disabled_reason'] == \
        'invalid credentials'
