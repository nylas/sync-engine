import json
import mockredis
import mock
import pytest
import platform
from inbox.ignition import engine_manager
from inbox.mailsync.frontend import HTTPFrontend
from inbox.mailsync.service import SyncService
from inbox.models import Account
from inbox.models.session import session_scope_by_shard_id
from inbox.scheduling.queue import QueueClient, QueuePopulator
from tests.util.base import add_generic_imap_account


host = platform.node()


@pytest.fixture(scope='function')
def mock_queue_client(monkeypatch):
    # Stop mockredis from trying to run Lua imports that aren't really needed.
    monkeypatch.setattr('mockredis.script.Script._import_lua_dependencies',
                        staticmethod(lambda *args, **kwargs: None))
    cl = QueueClient(zone='testzone')
    cl.redis = mockredis.MockRedis()
    return cl


def patched_sync_service(mock_queue_client, host=host, cpu_id=0):
    s = SyncService(process_identifier='{}:{}'.format(host, cpu_id),
                    cpu_id=cpu_id)
    s.queue_client = mock_queue_client
    s.start_sync = mock.Mock(
        side_effect=lambda aid: s.syncing_accounts.add(aid))
    return s


def purge_other_accounts(default_account=None):
    for key in engine_manager.engines:
        with session_scope_by_shard_id(key) as db_session:
            q = db_session.query(Account)
            if default_account is not None:
                q = q.filter(Account.id != default_account.id)
            q.delete(synchronize_session='fetch')
            db_session.commit()


def test_accounts_started_when_process_previously_assigned(
        default_account, config, mock_queue_client):
    config['SYNC_STEAL_ACCOUNTS'] = False
    mock_queue_client.enqueue(default_account.id)
    mock_queue_client.claim_next('{}:{}'.format(host, 0))
    s = patched_sync_service(mock_queue_client, host=host, cpu_id=0)
    assert s.accounts_to_sync() == {default_account.id}


def test_start_new_accounts_when_stealing_enabled(default_account,
                                                  config,
                                                  mock_queue_client):
    config['SYNC_STEAL_ACCOUNTS'] = True
    mock_queue_client.enqueue(default_account.id)
    s = patched_sync_service(mock_queue_client)
    s.poll()
    assert s.start_sync.call_count == 1
    assert s.start_sync.call_args == mock.call(default_account.id)


def test_dont_start_new_accounts_when_stealing_disabled(db, config,
                                                        default_account,
                                                        mock_queue_client):
    config['SYNC_STEAL_ACCOUNTS'] = False
    s = patched_sync_service(mock_queue_client)
    s.poll()
    assert s.start_sync.call_count == 0


def test_concurrent_syncs(db, default_account, config, mock_queue_client):
    config['SYNC_STEAL_ACCOUNTS'] = True
    mock_queue_client.enqueue(default_account.id)
    s1 = patched_sync_service(mock_queue_client, cpu_id=0)
    s2 = patched_sync_service(mock_queue_client, cpu_id=2)
    s1.poll()
    s2.poll()
    # Check that only one SyncService instance claims the account.
    assert s1.start_sync.call_count == 1
    assert s1.start_sync.call_args == mock.call(default_account.id)
    assert s2.start_sync.call_count == 0


def test_twice_queued_accounts_started_once(default_account,
                                            mock_queue_client):
    mock_queue_client.enqueue(default_account.id)
    mock_queue_client.enqueue(default_account.id)
    s = patched_sync_service(mock_queue_client)
    s.poll()
    s.poll()
    assert s.start_sync.call_count == 1


def test_queue_population(db, default_account, mock_queue_client):
    purge_other_accounts(default_account)
    qp = QueuePopulator(zone='testzone')
    qp.queue_client = mock_queue_client
    s = patched_sync_service(mock_queue_client)

    s.poll()
    assert s.start_sync.call_count == 0

    qp.enqueue_new_accounts()
    s.poll()
    assert s.start_sync.call_count == 1


def test_queue_population_limited_by_zone(db, default_account,
                                          mock_queue_client):
    purge_other_accounts(default_account)
    qp = QueuePopulator(zone='otherzone')
    qp.queue_client = mock_queue_client
    s = patched_sync_service(mock_queue_client)
    qp.enqueue_new_accounts()
    s.poll()
    assert s.start_sync.call_count == 0


def test_external_sync_disabling(db, mock_queue_client):
    purge_other_accounts()
    account = add_generic_imap_account(db.session, email_address='test@example.com')
    other_account = add_generic_imap_account(db.session,
                                     email_address='test2@example.com')
    qp = QueuePopulator(zone='testzone')
    qp.queue_client = mock_queue_client
    s = patched_sync_service(mock_queue_client)

    qp.enqueue_new_accounts()
    s.poll()
    s.poll()
    assert len(s.syncing_accounts) == 2

    account.mark_deleted()
    db.session.commit()
    assert account.sync_should_run is False
    assert account._sync_status['sync_disabled_reason'] == 'account deleted'

    account.mark_invalid()
    db.session.commit()
    assert account.sync_should_run is False
    assert account.sync_state == 'invalid'
    assert account._sync_status['sync_disabled_reason'] == \
        'invalid credentials'

    qp.unassign_disabled_accounts()
    s.poll()
    assert s.syncing_accounts == {other_account.id}


def test_http_unassignment(db, default_account, mock_queue_client):
    purge_other_accounts(default_account)
    qp = QueuePopulator(zone='testzone')
    qp.queue_client = mock_queue_client
    qp.enqueue_new_accounts()
    s = patched_sync_service(mock_queue_client)
    s.poll()

    frontend = HTTPFrontend(s, 16384, False, False)
    app = frontend._create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        resp = c.post(
            '/unassign', data=json.dumps({'account_id': default_account.id}),
            content_type='application/json')
        assert resp.status_code == 200
    db.session.expire_all()
    assert default_account.sync_host is None

    # Check that 409 is returned if account is not actually assigned to
    # process.
    with app.test_client() as c:
        resp = c.post(
            '/unassign', data=json.dumps({'account_id': default_account.id}),
            content_type='application/json')
        assert resp.status_code == 409


def test_start_accounts_w_sync_should_run_set(db, default_account,
                                              config,
                                              mock_queue_client):
    purge_other_accounts(default_account)
    config['SYNC_STEAL_ACCOUNTS'] = True
    default_account.sync_should_run = True
    db.session.commit()

    qp = QueuePopulator(zone='testzone')
    qp.queue_client = mock_queue_client
    qp.enqueue_new_accounts()
    s = patched_sync_service(mock_queue_client)

    s.poll()
    assert s.start_sync.call_count == 1


def test_dont_start_accounts_when_sync_should_run_is_none(db, default_account,
                                                          config,
                                                          mock_queue_client):
    purge_other_accounts(default_account)
    config['SYNC_STEAL_ACCOUNTS'] = True
    default_account.sync_should_run = False
    db.session.commit()

    qp = QueuePopulator(zone='testzone')
    qp.queue_client = mock_queue_client
    qp.enqueue_new_accounts()
    s = patched_sync_service(mock_queue_client)

    s.poll()
    assert s.start_sync.call_count == 0
