import random

import pytest
import gevent

from inbox.ignition import engine_manager
from inbox.models.session import session_scope, session_scope_by_shard_id
from inbox.models.account import Account
from inbox.models.action_log import ActionLog, schedule_action
from inbox.transactions.actions import SyncbackService

from tests.util.base import add_generic_imap_account


@pytest.fixture
def purge_accounts_and_actions():
    for key in engine_manager.engines:
        with session_scope_by_shard_id(key) as db_session:
            db_session.query(ActionLog).delete(synchronize_session=False)
            db_session.query(Account).delete(synchronize_session=False)
            db_session.commit()


@pytest.yield_fixture
def patched_enginemanager(monkeypatch):
    engines = {k: None for k in range(0, 6)}
    monkeypatch.setattr('inbox.ignition.engine_manager.engines', engines)
    yield
    monkeypatch.undo()


@pytest.yield_fixture
def patched_worker(monkeypatch):
    def run(self):
        with self.semaphore:
            with session_scope(self.account_id) as db_session:
                action_log_entry = db_session.query(ActionLog).get(
                    self.action_log_id)
                action_log_entry.status = 'successful'
                db_session.commit()
    monkeypatch.setattr('inbox.transactions.actions.SyncbackWorker._run', run)
    yield
    monkeypatch.undo()


def schedule_test_action(db_session, account):
    from inbox.models.category import Category

    category_type = 'label' if account.provider == 'gmail' else 'folder'
    category = Category.find_or_create(
        db_session, account.namespace.id, name=None,
        display_name='{}-{}'.format(account.id, random.randint(1, 356)),
        type_=category_type)
    db_session.flush()

    if category_type == 'folder':
        schedule_action('create_folder', category, account.namespace.id,
                        db_session)
    else:
        schedule_action('create_label', category, account.namespace.id,
                        db_session)
    db_session.commit()


def test_all_keys_are_assigned_exactly_once(patched_enginemanager):
    assigned_keys = []

    service = SyncbackService(syncback_id=0, cpu_id=0, total_cpus=2)
    assert service.keys == [0, 2, 4]
    assigned_keys.extend(service.keys)

    service = SyncbackService(syncback_id=0, cpu_id=1, total_cpus=2)
    assert service.keys == [1, 3, 5]
    assigned_keys.extend(service.keys)

    # All keys are assigned (therefore all accounts are assigned)
    assert set(engine_manager.engines.keys()) == set(assigned_keys)
    # No key is assigned more than once (and therefore, no account)
    assert len(assigned_keys) == len(set(assigned_keys))


def test_actions_are_claimed(purge_accounts_and_actions, patched_worker):
    with session_scope_by_shard_id(0) as db_session:
        account = add_generic_imap_account(
            db_session, email_address='{}@test.com'.format(0))
        schedule_test_action(db_session, account)

    with session_scope_by_shard_id(1) as db_session:
        account = add_generic_imap_account(
            db_session, email_address='{}@test.com'.format(1))
        schedule_test_action(db_session, account)

    service = SyncbackService(syncback_id=0, cpu_id=1, total_cpus=2)
    service.workers = set()
    service._process_log()

    gevent.joinall(list(service.workers))

    with session_scope_by_shard_id(0) as db_session:
        q = db_session.query(ActionLog)
        assert q.count() == 1
        assert all(a.status == 'pending' for a in q)

    with session_scope_by_shard_id(1) as db_session:
        q = db_session.query(ActionLog)
        assert q.count() == 1
        assert all(a.status != 'pending' for a in q)


def test_actions_claimed_by_a_single_service(purge_accounts_and_actions,
                                             patched_worker):
    actionlogs = []
    for key in (0, 1):
        with session_scope_by_shard_id(key) as db_session:
            account = add_generic_imap_account(
                db_session,
                email_address='{}@test.com'.format(key))
            schedule_test_action(db_session, account)
            actionlogs += [db_session.query(ActionLog).one().id]

    services = []
    for cpu_id in (0, 1):
        service = SyncbackService(syncback_id=0, cpu_id=cpu_id, total_cpus=2)
        service.workers = set()
        service._process_log()
        services.append(service)

    for i, service in enumerate(services):
        assert len(service.workers) == 1
        assert list(service.workers)[0].action_log_id == actionlogs[i]
        gevent.joinall(list(service.workers))


@pytest.mark.skipif(True, reason='Test if causing Jenkins build to fail')
def test_actions_for_invalid_accounts_are_skipped(purge_accounts_and_actions,
                                                  patched_worker):
    with session_scope_by_shard_id(0) as db_session:
        account = add_generic_imap_account(
            db_session, email_address='person@test.com')
        schedule_test_action(db_session, account)
        namespace_id = account.namespace.id
        count = db_session.query(ActionLog).filter(
            ActionLog.namespace_id == namespace_id).count()
        assert account.sync_state != 'invalid'

        another_account = add_generic_imap_account(
            db_session, email_address='another@test.com')
        schedule_test_action(db_session, another_account)
        another_namespace_id = another_account.namespace.id
        another_count = db_session.query(ActionLog).filter(
            ActionLog.namespace_id == another_namespace_id).count()
        assert another_account.sync_state != 'invalid'

        account.mark_invalid()
        db_session.commit()

    service = SyncbackService(syncback_id=0, cpu_id=0, total_cpus=2)
    service._process_log()

    while len(service.workers) >= 1:
        gevent.sleep(0.1)
    gevent.killall(service.workers)

    with session_scope_by_shard_id(0) as db_session:
        q = db_session.query(ActionLog).filter(
            ActionLog.namespace_id == namespace_id,
            ActionLog.status == 'pending')
        assert q.count() == count

        q = db_session.query(ActionLog).filter(
            ActionLog.namespace_id == another_namespace_id)
        assert q.filter(ActionLog.status == 'pending').count() == 0
        assert q.filter(ActionLog.status == 'successful').count() == another_count
