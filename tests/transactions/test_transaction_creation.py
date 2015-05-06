from sqlalchemy import desc
from inbox.models import Transaction, Tag, Calendar
from tests.util.base import add_fake_message, add_fake_thread, add_fake_event

NAMESPACE_ID = 1


def get_latest_transaction(db_session, object_type, record_id, namespace_id):
    return db_session.query(Transaction).filter(
        Transaction.namespace_id == namespace_id,
        Transaction.object_type == object_type,
        Transaction.record_id == record_id). \
        order_by(desc(Transaction.id)).first()


def test_thread_insert_creates_transaction(db):
    thr = add_fake_thread(db.session, NAMESPACE_ID)
    transaction = get_latest_transaction(db.session, 'thread', thr.id,
                                         NAMESPACE_ID)
    assert transaction.command == 'insert'


def test_thread_tag_updates_create_transactions(db):
    thr = add_fake_thread(db.session, NAMESPACE_ID)

    new_tag = Tag(name='foo', namespace_id=NAMESPACE_ID)
    db.session.add(new_tag)
    db.session.commit()

    thr.apply_tag(new_tag)
    transaction = get_latest_transaction(db.session, 'thread', thr.id,
                                         NAMESPACE_ID)
    assert transaction.command == 'update'

    thr.remove_tag(new_tag)
    next_transaction = get_latest_transaction(db.session, 'thread', thr.id,
                                              NAMESPACE_ID)
    assert next_transaction.id != transaction


def test_message_insert_creates_transaction(db):
    with db.session.no_autoflush:
        thr = add_fake_thread(db.session, NAMESPACE_ID)
        msg = add_fake_message(db.session, NAMESPACE_ID, thr)
        transaction = get_latest_transaction(db.session, 'message', msg.id,
                                             NAMESPACE_ID)
        assert transaction.command == 'insert'

        # Test that the thread gets revised too
        transaction = get_latest_transaction(db.session, 'thread', thr.id,
                                             NAMESPACE_ID)
        assert transaction.command == 'update'


def test_message_updates_create_transaction(db):
    with db.session.no_autoflush:
        thr = add_fake_thread(db.session, NAMESPACE_ID)
        msg = add_fake_message(db.session, NAMESPACE_ID, thr)

        msg.is_read = True
        db.session.commit()
        transaction = get_latest_transaction(db.session, 'message', msg.id,
                                             NAMESPACE_ID)
        assert transaction.record_id == msg.id
        assert transaction.object_type == 'message'
        assert transaction.command == 'update'

        msg = add_fake_message(db.session, NAMESPACE_ID, thr)
        msg.is_draft = True
        db.session.commit()
        transaction = get_latest_transaction(db.session, 'message', msg.id,
                                             NAMESPACE_ID)
        assert transaction.record_id == msg.id
        assert transaction.object_type == 'message'
        assert transaction.command == 'update'


def test_event_insert_creates_transaction(db):
    with db.session.no_autoflush:
        event = add_fake_event(db.session, NAMESPACE_ID)
        transaction = get_latest_transaction(db.session, 'event',
                                             event.id, NAMESPACE_ID)
        assert transaction.record_id == event.id
        assert transaction.object_type == 'event'
        assert transaction.command == 'insert'


def test_transactions_created_for_calendars(db):
    calendar = Calendar(
        namespace_id=NAMESPACE_ID,
        name='New Calendar',
        uid='uid')
    db.session.add(calendar)
    db.session.commit()
    transaction = get_latest_transaction(db.session, 'calendar',
                                         calendar.id, NAMESPACE_ID)
    assert transaction.record_id == calendar.id
    assert transaction.object_type == 'calendar'
    assert transaction.command == 'insert'

    calendar.name = 'Updated Calendar'
    db.session.commit()
    transaction = get_latest_transaction(db.session, 'calendar',
                                         calendar.id, NAMESPACE_ID)
    assert transaction.record_id == calendar.id
    assert transaction.object_type == 'calendar'
    assert transaction.command == 'update'

    db.session.delete(calendar)
    db.session.commit()
    transaction = get_latest_transaction(db.session, 'calendar',
                                         calendar.id, NAMESPACE_ID)
    assert transaction.record_id == calendar.id
    assert transaction.object_type == 'calendar'
    assert transaction.command == 'delete'


def test_object_deletions_create_transaction(db):
    with db.session.no_autoflush:
        thr = add_fake_thread(db.session, NAMESPACE_ID)
        msg = add_fake_message(db.session, NAMESPACE_ID, thr)
        db.session.delete(msg)
        db.session.commit()
        transaction = get_latest_transaction(db.session, 'message', msg.id,
                                             NAMESPACE_ID)
        assert transaction.record_id == msg.id
        assert transaction.object_type == 'message'
        assert transaction.command == 'delete'

        db.session.delete(thr)
        db.session.commit()
        transaction = get_latest_transaction(db.session, 'thread', thr.id,
                                             NAMESPACE_ID)
        assert transaction.record_id == thr.id
        assert transaction.object_type == 'thread'
        assert transaction.command == 'delete'
