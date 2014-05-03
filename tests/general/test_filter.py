from datetime import datetime
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

    timetuple = received_date.utctimetuple()

    early = datetime(timetuple.tm_year, timetuple.tm_mon, timetuple.tm_mday,
                     timetuple.tm_hour, timetuple.tm_min,
                     timetuple.tm_sec).utctimetuple()
    early_ts = calendar.timegm(early)

    late = datetime(timetuple.tm_year, timetuple.tm_mon, timetuple.tm_mday,
                    timetuple.tm_hour, timetuple.tm_min + 1,
                    timetuple.tm_sec).utctimetuple()
    late_ts = calendar.timegm(late)

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
                            to_addr=to_addr,
                            limit=3)
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1
