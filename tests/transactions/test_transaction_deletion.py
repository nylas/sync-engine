import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import desc

from inbox.models import Transaction
from inbox.models.util import purge_transactions


def get_latest_transaction(db_session, namespace_id):
    return db_session.query(Transaction).filter(
        Transaction.namespace_id == namespace_id).\
        order_by(desc(Transaction.id)).first()


def create_transaction(db, created_at, namespace_id):
    t = Transaction(created_at=created_at,
                    updated_at=datetime.now(),
                    namespace_id=namespace_id,
                    object_type='message',
                    command='insert',
                    record_id=random.randint(1, 9999),
                    object_public_id=uuid.uuid4().hex)
    db.session.add(t)
    db.session.commit()
    return t


def test_transaction_deletion(db, default_namespace):
    # Test that transaction deletion respects the days_ago
    # parameter. Arbitrarily chose 30 days for `days_ago`
    now = datetime.now()
    # Transactions created less than 30 days ago should not be deleted
    t0 = create_transaction(db, now, default_namespace.id)
    create_transaction(db, now - timedelta(days=29), default_namespace.id)
    create_transaction(db, now - timedelta(days=30), default_namespace.id)

    # Transactions older than 30 days should be deleted
    for i in xrange(10):
        create_transaction(db, now - timedelta(days=31 + i),
                           default_namespace.id)

    shard_id = (default_namespace.id >> 48)
    query = "SELECT count(id) FROM transaction WHERE namespace_id={}".\
        format(default_namespace.id)
    all_transactions = db.session.execute(query).scalar()
    date_query = ("SELECT count(id) FROM transaction WHERE created_at < "
                  "DATE_SUB(now(), INTERVAL 30 day)")
    older_than_thirty_days = db.session.execute(date_query).scalar()

    # Ensure no transactions are deleted during a dry run
    purge_transactions(shard_id, days_ago=30, dry_run=True)
    assert db.session.execute(query).scalar() == all_transactions

    # Delete all transactions older than 30 days
    purge_transactions(shard_id, days_ago=30, dry_run=False)
    assert all_transactions - older_than_thirty_days == \
        db.session.execute(query).scalar()

    query = "SELECT count(id) FROM transaction WHERE namespace_id={}".\
        format(default_namespace.id)
    all_transactions = db.session.execute(query).scalar()

    date_query = ("SELECT count(id) FROM transaction WHERE created_at < "
                  "DATE_SUB(now(), INTERVAL 1 day)")
    older_than_one_day = db.session.execute(date_query).scalar()
    # Delete all transactions older than 1 day
    purge_transactions(shard_id, days_ago=1, dry_run=False)
    assert all_transactions - older_than_one_day == \
        db.session.execute(query).scalar()

    latest_transaction = get_latest_transaction(db.session,
                                                default_namespace.id)
    assert latest_transaction.id == t0.id
