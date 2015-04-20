from tests.util.base import add_fake_thread, add_fake_message


def test_unread(db, default_namespace):
    from inbox.models import Thread

    thread = add_fake_thread(db.session, default_namespace.id)
    thread_id = thread.id
    message = add_fake_message(db.session, default_namespace.id, thread)

    unread_tag = default_namespace.tags['unread']

    assert unread_tag in thread.tags
    assert message.is_read is False

    thread.remove_tag(unread_tag)
    db.session.commit()

    thread = db.session.query(Thread).get(thread_id)
    assert unread_tag not in thread.tags

    for m in thread.messages:
        assert m.is_read is True

    thread.apply_tag(unread_tag)
    db.session.commit()

    thread = db.session.query(Thread).get(thread_id)
    assert unread_tag in thread.tags

    for m in thread.messages:
        assert m.is_read is False
