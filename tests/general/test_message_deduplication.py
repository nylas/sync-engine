from tests.util.base import (add_fake_thread, add_fake_account,
                             new_message_from_synced)


def test_data_deduplication(db, default_namespace, raw_message):
    thread = add_fake_thread(db.session, default_namespace.id)
    msg = new_message_from_synced(db, default_namespace.account, raw_message)
    msg.thread = thread
    db.session.add(msg)
    db.session.commit()

    account = add_fake_account(db.session)
    thread = add_fake_thread(db.session, account.namespace.id)
    duplicate_msg = new_message_from_synced(db, account, raw_message)
    duplicate_msg.thread = thread
    db.session.add(duplicate_msg)
    db.session.commit()

    assert len(msg.parts) == len(duplicate_msg.parts)

    for i in range(len(msg.parts)):
        msg_block = msg.parts[i].block
        duplicate_msg_block = duplicate_msg.parts[i].block

        assert msg_block.namespace_id == msg.namespace_id
        assert duplicate_msg_block.namespace_id == duplicate_msg.namespace_id

        assert msg_block.size == duplicate_msg_block.size
        assert msg_block.data_sha256 == duplicate_msg_block.data_sha256
        assert msg_block.data == duplicate_msg_block.data
