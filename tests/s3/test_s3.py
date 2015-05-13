import os

import pytest

from tests.util.base import (TestDB, absolute_path, add_fake_account,
                             add_fake_thread, raw_message,
                             new_message_from_synced)

__all__ = ['raw_message']


# Use a config that sets STORE_MESSAGES_ON_S3=True
@pytest.fixture(scope='session', autouse=True)
def config():
    from inbox.config import config
    assert 'INBOX_ENV' in os.environ and \
        os.environ['INBOX_ENV'] == 'test', \
        "INBOX_ENV must be 'test' to run tests"

    assert 'AWS_ACCESS_KEY_ID' in config and 'AWS_SECRET_ACCESS_KEY' in config
    assert 'MESSAGE_STORE_BUCKET_NAME' in config

    config['STORE_MESSAGES_ON_S3'] = True
    return config


# Use a testdb dump that has messages that were uploaded to s3.
@pytest.yield_fixture(scope='function')
def s3_db(config):
    dumpfile = absolute_path('data/s3_dump.sql')
    testdb = TestDB(config, dumpfile)
    yield testdb
    testdb.teardown()


def test_data_retrieval(s3_db):
    from inbox.models import Message

    # Message 1, 2 in s3_db are identical messages that have
    # different namespace_ids.

    msg = s3_db.session.query(Message).get(1)
    namespace_id = msg.namespace_id

    duplicate_msg = s3_db.session.query(Message).get(2)
    other_namespace_id = duplicate_msg.namespace_id

    assert namespace_id != other_namespace_id

    assert len(msg.parts) == len(duplicate_msg.parts)

    for i in range(len(msg.parts)):
        msg_block = msg.parts[i].block
        assert msg_block.namespace_id == msg.namespace_id

        duplicate_msg_block = duplicate_msg.parts[i].block
        assert duplicate_msg_block.namespace_id == duplicate_msg.namespace_id

        assert msg_block.size == duplicate_msg_block.size
        assert msg_block.data_sha256 == duplicate_msg_block.data_sha256
        assert msg_block.data == duplicate_msg_block.data


# # Run this test only after adding write-permissions on the test s3 bucket for
# # the test user.
@pytest.mark.skipif(True, reason='requires s3 write-permissions')
def test_data_deduplication(s3_db, raw_message):
    from inbox.models import Namespace

    default_namespace = s3_db.session.query(Namespace).get(1)
    thread = add_fake_thread(s3_db.session, default_namespace.id)
    msg = new_message_from_synced(s3_db, default_namespace.account, raw_message)
    msg.thread = thread
    s3_db.session.add(msg)
    s3_db.session.commit()

    account = add_fake_account(s3_db.session)
    thread = add_fake_thread(s3_db.session, account.namespace.id)
    duplicate_msg = new_message_from_synced(s3_db, account, raw_message)
    duplicate_msg.thread = thread
    s3_db.session.add(duplicate_msg)
    s3_db.session.commit()

    assert len(msg.parts) == len(duplicate_msg.parts)

    for i in range(len(msg.parts)):
        msg_block = msg.parts[i].block
        duplicate_msg_block = duplicate_msg.parts[i].block

        assert msg_block.namespace_id == msg.namespace_id
        assert duplicate_msg_block.namespace_id == duplicate_msg.namespace_id

        assert msg_block.size == duplicate_msg_block.size
        assert msg_block.data_sha256 == duplicate_msg_block.data_sha256
        assert msg_block.data == duplicate_msg_block.data
