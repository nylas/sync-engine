from tests.util.base import add_fake_message, add_fake_category


def test_adding_and_removing_message_on_thread_increments_version(
        db, thread, default_namespace):
    assert thread.version == 0
    message = add_fake_message(db.session, default_namespace.id, thread)
    assert thread.version == 1
    thread.messages.remove(message)
    db.session.commit()
    assert thread.version == 2


def test_updating_message_read_starred_increments_version(
        db, thread, default_namespace):
    assert thread.version == 0

    message = add_fake_message(db.session, default_namespace.id, thread)
    assert thread.version == 1

    # Modifying a non-propagated attribute does /not/ increment thread.version
    # (Non-propagated attributes on non-draft messages are technically
    # never modified)
    message.subject = 'Jen nova temo'
    db.session.commit()
    assert thread.version == 1

    # Modifying message.is_read /is_starred increments the thread.version
    message.is_read = not message.is_read
    db.session.commit()
    assert thread.version == 2

    message.is_starred = not message.is_starred
    db.session.commit()
    assert thread.version == 3


def test_updating_message_categories_increments_version(
        db, thread, default_namespace):
    assert thread.version == 0

    message = add_fake_message(db.session, default_namespace.id, thread)
    category = add_fake_category(db.session, default_namespace.id,
                                 'mia kategorio')

    # Modifying message's categories increments the thread.version
    message.categories = [category]
    db.session.commit()

    assert thread.version == 2
