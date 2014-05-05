import datetime
import calendar

from tests.data.messages.message import (subject, delivered_to, sender,
                                         to_addr, from_addr, received_date)
from tests.util.base import config
config()

from inbox.util.filter import DatabaseFilter
from inbox.server.models.tables.base import register_backends
register_backends()

NAMESPACE_ID = 1


def test_filters(db):
    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject=subject)
    assert filter.message_query(db.session).count() == 1
    assert filter.thread_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            email=delivered_to)
    assert filter.message_query(db.session).count() > 1
    assert filter.thread_query(db.session).count() > 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            email=sender)
    assert filter.message_query(db.session).count() == 1
    assert filter.thread_query(db.session).count() == 1

    early_time = received_date - datetime.timedelta(hours=1)
    late_time = received_date + datetime.timedelta(hours=1)
    early_ts = calendar.timegm(early_time.utctimetuple())
    late_ts = calendar.timegm(late_time.utctimetuple())

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject=subject,
                            started_before=early_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject=subject,
                            started_before=late_ts)

    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject=subject,
                            last_message_after=early_ts)
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject=subject,
                            last_message_after=late_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject=subject,
                            last_message_before=early_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            subject=subject,
                            last_message_before=late_ts)
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            to_addr=to_addr,
                            from_addr=from_addr)

    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = DatabaseFilter(namespace_id=NAMESPACE_ID,
                            to_addr='inboxapptest@gmail.com',
                            limit=3)
    assert filter.thread_query(db.session).count() == 3
    assert filter.message_query(db.session).count() == 3
