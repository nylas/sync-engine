from inbox.ignition import EngineManager
from inbox.models import Namespace
from inbox.models.session import session_scope_by_shard_id



def test_pools_shared_by_host():
    databases = [
        {
            'HOSTNAME': 'host_a',
            'PORT': 3306,
            'SHARDS': [
                {
                    'ID': 0,
                    'SCHEMA_NAME': 'schema_0'
                },
                {
                    'ID': 1,
                    'SCHEMA_NAME': 'schema_1'
                }
            ]
        },
        {
            'HOSTNAME': 'host_b',
            'PORT': 3306,
            'SHARDS': [
                {
                    'ID': 2,
                    'SCHEMA_NAME': 'schema_2'
                },
                {
                    'ID': 3,
                    'SCHEMA_NAME': 'schema_3'
                }
            ]
        }
    ]
    users = {
        'host_a': {'USER': 'testuser', 'PASSWORD': 'testpass'},
        'host_b': {'USER': 'testuser', 'PASSWORD': 'testpass'}
    }

    engine_manager = EngineManager(databases, users)
    assert engine_manager.engines[0].pool is engine_manager.engines[1].pool
    assert engine_manager.engines[2].pool is engine_manager.engines[3].pool
    assert engine_manager.engines[0].pool != engine_manager.engines[2].pool


def test_checkout():
    with session_scope_by_shard_id(0) as db_session:
        ns = Namespace()
        db_session.add(ns)
        db_session.commit()
        assert ns.id >> 48 == 0

    with session_scope_by_shard_id(1) as db_session:
        ns = Namespace()
        db_session.add(ns)
        db_session.commit()
        assert ns.id >> 48 == 1

    with session_scope_by_shard_id(0) as db_session:
        ns = db_session.query(Namespace).first()
        assert db_session.connection().info['selected_db'] == 'test'

    with session_scope_by_shard_id(1) as db_session:
        ns = db_session.query(Namespace).first()
        assert db_session.connection().info['selected_db'] == 'test_1'

    with session_scope_by_shard_id(0) as db_session_0, \
            session_scope_by_shard_id(1) as db_session_1:
        ns0 = db_session_0.query(Namespace).first()
        assert ns0.id >> 48 == 0
        ns1 = db_session_1.query(Namespace).first()
        assert ns1.id >> 48 == 1


