import pytest
from sqlalchemy import desc
from inbox.models import Transaction, Tag
from inbox.models.session import session_scope
from tests.util.base import add_fake_message, add_fake_thread

NAMESPACE_ID = 1


def get_latest_transaction(db_session, object_type, record_id, namespace_id):
    return db_session.query(Transaction).filter(
        Transaction.namespace_id == namespace_id,
        Transaction.object_type == object_type,
        Transaction.record_id == record_id). \
        order_by(desc(Transaction.id)).first()


def test_thread_insert_creates_transaction(db):
    with session_scope() as db_session:
        thr = add_fake_thread(db_session, NAMESPACE_ID)
        transaction = get_latest_transaction(db_session, 'thread', thr.id,
                                             NAMESPACE_ID)
        assert transaction.command == 'insert'
        assert transaction.snapshot


def test_thread_tag_updates_create_transactions(db):
    with session_scope() as db_session:
        thr = add_fake_thread(db_session, NAMESPACE_ID)

        new_tag = Tag(name='foo', namespace_id=NAMESPACE_ID)
        db_session.add(new_tag)
        db_session.commit()

        thr.apply_tag(new_tag)
        transaction = get_latest_transaction(db_session, 'thread', thr.id,
                                             NAMESPACE_ID)
        assert transaction.command == 'update'

        thr.remove_tag(new_tag)
        next_transaction = get_latest_transaction(db_session, 'thread', thr.id,
                                                  NAMESPACE_ID)
        assert next_transaction.id != transaction


def test_message_insert_creates_transaction(db):
    with session_scope() as db_session:
        with db_session.no_autoflush:
            thr = add_fake_thread(db_session, NAMESPACE_ID)
            msg = add_fake_message(db_session, NAMESPACE_ID, thr)
            transaction = get_latest_transaction(db_session, 'message', msg.id,
                                                 NAMESPACE_ID)
            assert transaction.command == 'insert'

            # Test that the thread gets revised too
            transaction = get_latest_transaction(db_session, 'thread', thr.id,
                                                 NAMESPACE_ID)
            assert transaction.command == 'update'


def test_message_updates_create_transaction(db):
    with session_scope() as db_session:
        with db_session.no_autoflush:
            thr = add_fake_thread(db_session, NAMESPACE_ID)
            msg = add_fake_message(db_session, NAMESPACE_ID, thr)

            msg.is_read = True
            db_session.commit()
            transaction = get_latest_transaction(db_session, 'message', msg.id,
                                                 NAMESPACE_ID)
            assert transaction.record_id == msg.id
            assert transaction.object_type == 'message'
            assert transaction.command == 'update'

            msg = add_fake_message(db_session, NAMESPACE_ID, thr)
            msg.state = 'sent'
            db_session.commit()
            transaction = get_latest_transaction(db_session, 'message', msg.id,
                                                 NAMESPACE_ID)
            assert transaction.record_id == msg.id
            assert transaction.object_type == 'message'
            assert transaction.command == 'update'

            msg = add_fake_message(db_session, NAMESPACE_ID, thr)
            msg.is_draft = True
            db_session.commit()
            transaction = get_latest_transaction(db_session, 'message', msg.id,
                                                 NAMESPACE_ID)
            assert transaction.record_id == msg.id
            assert transaction.object_type == 'message'
            assert transaction.command == 'update'


def test_event_insert_creates_transaction(db):
    from tests.general.events.default_event import default_event
    with session_scope() as db_session:
        with db_session.no_autoflush:
            event = default_event(db_session)
            transaction = get_latest_transaction(db_session, 'event',
                                                 event.id, NAMESPACE_ID)
            assert transaction.record_id == event.id
            assert transaction.object_type == 'event'
            assert transaction.command == 'insert'


def test_participant_update_creates_transaction(db):
    from tests.general.events.default_event import default_event
    from inbox.models.participant import Participant
    with session_scope() as db_session:
        with db_session.no_autoflush:
            event = default_event(db_session)
            participant = Participant(email_address="foo@example.com")
            event.participants = [participant]
            db_session.commit()

            transaction = get_latest_transaction(db_session, 'event',
                                                 event.id, NAMESPACE_ID)
            assert transaction.record_id == event.id
            assert transaction.object_type == 'event'
            assert transaction.command == 'update'


def test_object_deletions_create_transaction(db):
    with session_scope() as db_session:
        with db_session.no_autoflush:
            thr = add_fake_thread(db_session, NAMESPACE_ID)
            msg = add_fake_message(db_session, NAMESPACE_ID, thr)
            db_session.delete(msg)
            db_session.commit()
            transaction = get_latest_transaction(db_session, 'message', msg.id,
                                                 NAMESPACE_ID)
            assert transaction.record_id == msg.id
            assert transaction.object_type == 'message'
            assert transaction.command == 'delete'

            db_session.delete(thr)
            db_session.commit()
            transaction = get_latest_transaction(db_session, 'thread', thr.id,
                                                 NAMESPACE_ID)
            assert transaction.record_id == thr.id
            assert transaction.object_type == 'thread'
            assert transaction.command == 'delete'
