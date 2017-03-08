import json
import mock
import pytest
import platform
from inbox.ignition import engine_manager
from inbox.mailsync.frontend import SyncHTTPFrontend
from inbox.mailsync.service import SyncService
from inbox.models import Account
from inbox.models.session import session_scope_by_shard_id
from inbox.test.util.base import add_generic_imap_account


host = platform.node()


def patched_sync_service(db, host=host, process_number=0):
    s = SyncService(process_identifier='{}:{}'.format(host, process_number),
                    process_number=process_number)

    def start_sync(aid):
        acc = db.session.query(Account).get(aid)
        acc.sync_host = s.process_identifier
        acc.sync_started()
        s.syncing_accounts.add(aid)
        db.session.commit()
        return True

    s.start_sync = mock.Mock(side_effect=start_sync)
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
        db, default_account, config):
    config['SYNC_STEAL_ACCOUNTS'] = False
    default_account.desired_sync_host = '{}:{}'.format(host, 0)
    db.session.commit()
    s = patched_sync_service(db, host=host, process_number=0)
    assert s.account_ids_to_sync() == {default_account.id}


def test_start_new_accounts_when_stealing_enabled(monkeypatch, db,
                                                  default_account, config):
    config['SYNC_STEAL_ACCOUNTS'] = True

    purge_other_accounts(default_account)
    s = patched_sync_service(db)
    default_account.sync_host = None
    db.session.commit()

    s.poll_shared_queue({'queue_name': 'foo', 'id': default_account.id})
    assert s.start_sync.call_count == 1
    assert s.start_sync.call_args == mock.call(default_account.id)


def test_dont_start_accounts_if_over_ppa_limit(monkeypatch, db,
                                               default_account, config):
    config['SYNC_STEAL_ACCOUNTS'] = True

    purge_other_accounts(default_account)
    default_account.sync_host = None
    db.session.commit()
    s = patched_sync_service(db)
    s._pending_avgs_provider = mock.Mock()
    s._pending_avgs_provider.get_pending_avgs = lambda *args: {15: 11}

    s.poll_shared_queue({'queue_name': 'foo', 'id': default_account.id})
    assert s.start_sync.call_count == 0


def test_dont_start_new_accounts_when_stealing_disabled(db, config,
                                                        default_account):
    config['SYNC_STEAL_ACCOUNTS'] = False
    s = patched_sync_service(db)
    default_account.sync_host = None
    db.session.commit()
    s.poll_shared_queue({'queue_name': 'foo', 'id': default_account.id})
    assert s.start_sync.call_count == 0


def test_concurrent_syncs(monkeypatch, db, default_account, config):
    config['SYNC_STEAL_ACCOUNTS'] = True

    purge_other_accounts(default_account)
    s1 = patched_sync_service(db, process_number=0)
    s2 = patched_sync_service(db, process_number=2)
    default_account.desired_sync_host = s1.process_identifier
    db.session.commit()
    s1.poll({'queue_name': 'foo'})
    s2.poll({'queue_name': 'foo'})
    # Check that only one SyncService instance claims the account.
    assert s1.start_sync.call_count == 1
    assert s1.start_sync.call_args == mock.call(default_account.id)
    assert s2.start_sync.call_count == 0


def test_twice_queued_accounts_started_once(monkeypatch, db, default_account):
    purge_other_accounts(default_account)
    s = patched_sync_service(db)
    default_account.desired_sync_host = s.process_identifier
    db.session.commit()
    s.poll({'queue_name': 'foo'})
    s.poll({'queue_name': 'foo'})
    assert default_account.sync_host == s.process_identifier
    assert s.start_sync.call_count == 1


def test_external_sync_disabling(monkeypatch, db):
    purge_other_accounts()
    account = add_generic_imap_account(db.session,
                                       email_address='test@example.com')
    other_account = add_generic_imap_account(
        db.session, email_address='test2@example.com')
    account.sync_host = None
    account.desired_sync_host = None
    other_account.sync_host = None
    other_account.desired_sync_host = None
    db.session.commit()
    s = patched_sync_service(db)

    s.poll_shared_queue({'queue_name': 'foo', 'id': account.id})
    s.poll_shared_queue({'queue_name': 'foo', 'id': other_account.id})
    assert len(s.syncing_accounts) == 2

    account.mark_for_deletion()
    db.session.commit()
    assert account.sync_should_run is False
    assert account._sync_status['sync_disabled_reason'] == 'account deleted'

    account.mark_invalid()
    db.session.commit()
    assert account.sync_should_run is False
    assert account.sync_state == 'invalid'
    assert account._sync_status['sync_disabled_reason'] == \
        'invalid credentials'

    s.poll({'queue_name': 'foo'})
    assert s.syncing_accounts == {other_account.id}


def test_http_frontend(db, default_account, monkeypatch):
    s = patched_sync_service(db)
    s.poll({'queue_name': 'foo'})

    monkeypatch.setattr('pympler.muppy.get_objects', lambda *args: [])
    monkeypatch.setattr('pympler.summary.summarize', lambda *args: [])

    frontend = SyncHTTPFrontend(s, 16384, trace_greenlets=True, profile=True)
    app = frontend._create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        resp = c.get('/profile')
        assert resp.status_code == 200
        resp = c.get('/load')
        assert resp.status_code == 200
        resp = c.get('/mem')
        assert resp.status_code == 200
    monkeypatch.undo()


def test_http_unassignment(db, default_account):
    purge_other_accounts(default_account)
    s = patched_sync_service(db)
    default_account.desired_sync_host = None
    default_account.sync_host = None
    db.session.commit()
    s.poll_shared_queue({'queue_name': 'foo', 'id': default_account.id})

    frontend = SyncHTTPFrontend(s, 16384, False, False)
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


@pytest.mark.parametrize("sync_state", ["running", "stopped", "invalid", None])
def test_start_accounts_w_sync_should_run_set(monkeypatch, db, default_account,
                                              config,
                                              sync_state):
    purge_other_accounts(default_account)
    config['SYNC_STEAL_ACCOUNTS'] = True
    default_account.sync_should_run = True
    default_account.sync_state = sync_state
    default_account.sync_host = None
    default_account.desired_sync_host = None
    db.session.commit()

    s = patched_sync_service(db)
    s.poll_shared_queue({'queue_name': 'foo', 'id': default_account.id})
    assert s.start_sync.call_count == 1
