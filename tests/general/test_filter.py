from datetime import datetime
import calendar

from tests.util.base import config
config()

from inbox.util.filter import DatabaseFilter
from inbox.server.models.tables.base import register_backends
register_backends()

NAMESPACE_ID = 1


def test_filters(db):
    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject='Welcome to Gmail')
    assert filter.message_query(db.session).count() == 1
    assert filter.thread_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            email='inboxapptest@gmail.com')
    assert filter.message_query(db.session).count() > 1
    assert filter.thread_query(db.session).count() > 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            email='mail-noreply@google.com')
    assert filter.message_query(db.session).count() > 1
    assert filter.thread_query(db.session).count() > 1

    early_ts = calendar.timegm(
        datetime(2013, 8, 20, 18, 2, 00).utctimetuple())
    late_ts = calendar.timegm(
        datetime(2013, 8, 20, 18, 3, 00).utctimetuple())

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject='Welcome to Gmail',
                            started_before=early_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject='Welcome to Gmail',
                            started_before=late_ts)
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject='Welcome to Gmail',
                            last_message_after=early_ts)
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject='Welcome to Gmail',
                            last_message_after=late_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject='Welcome to Gmail',
                            last_message_before=early_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject='Welcome to Gmail',
                            last_message_before=late_ts)
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            to_addr='inboxapptest@gmail.com',
                            from_addr='no-reply@accounts.google.com')
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            to_addr='inboxapptest@gmail.com',
                            limit=3)
    assert filter.thread_query(db.session).count() == 3
    assert filter.message_query(db.session).count() == 3
