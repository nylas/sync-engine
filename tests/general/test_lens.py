import pytest
import datetime
import calendar

from sqlalchemy import desc

from tests.util.base import config, api_client
config()

from inbox.models import (register_backends, Lens, Message, SpoolMessage,
                          Transaction)
register_backends()

NAMESPACE_ID = 1


def test_lens_db_filter(db):
    message = db.session.query(Message).filter_by(id=2).one()

    subject = message.subject
    to_addr = message.to_addr[0][1]
    from_addr = message.from_addr[0][1]
    received_date = message.received_date

    filter = Lens(namespace_id=NAMESPACE_ID,
                  subject=subject)
    assert filter.message_query(db.session).count() == 1
    assert filter.thread_query(db.session).count() == 1

    filter = Lens(namespace_id=NAMESPACE_ID,
                  any_email='inboxapptest@gmail.com')
    assert filter.message_query(db.session).count() > 1
    assert filter.thread_query(db.session).count() > 1

    filter = Lens(namespace_id=NAMESPACE_ID,
                  any_email=from_addr)
    assert filter.message_query(db.session).count() == 1
    assert filter.thread_query(db.session).count() == 1

    early_time = received_date - datetime.timedelta(seconds=1)
    late_time = received_date + datetime.timedelta(seconds=1)
    early_ts = calendar.timegm(early_time.utctimetuple())
    late_ts = calendar.timegm(late_time.utctimetuple())

    filter = Lens(namespace_id=NAMESPACE_ID,
                  subject=subject,
                  started_before=early_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = Lens(namespace_id=NAMESPACE_ID,
                  subject=subject,
                  started_before=late_ts)

    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = Lens(namespace_id=NAMESPACE_ID,
                  subject=subject,
                  last_message_after=early_ts)
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = Lens(namespace_id=NAMESPACE_ID,
                  subject=subject,
                  last_message_after=late_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = Lens(namespace_id=NAMESPACE_ID,
                  subject=subject,
                  last_message_before=early_ts)
    assert filter.thread_query(db.session).count() == 0
    assert filter.message_query(db.session).count() == 0

    filter = Lens(namespace_id=NAMESPACE_ID,
                  subject=subject,
                  last_message_before=late_ts)
    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = Lens(namespace_id=NAMESPACE_ID,
                  to_addr=to_addr,
                  from_addr=from_addr)

    assert filter.thread_query(db.session).count() == 1
    assert filter.message_query(db.session).count() == 1

    filter = Lens(namespace_id=NAMESPACE_ID,
                  to_addr='inboxapptest@gmail.com')
    assert filter.thread_query(db.session, limit=3).count() == 3
    assert filter.message_query(db.session, limit=3).count() == 3


def test_lens_tx(api_client, db):
    api_client.post_data('/drafts', {
        'subject': 'Calaveras Dome / Hammer Dome',
        'to': [{'name': 'Somebody', 'email': 'somebody@example.com'}],
        'cc': [{'name': 'Another Person', 'email': 'another@example.com'}]
    })

    transaction = db.session.query(Transaction). \
        filter(Transaction.table_name == 'spoolmessage'). \
        order_by(desc(Transaction.id)).first()

    draft = db.session.query(SpoolMessage). \
        order_by(desc(SpoolMessage.id)).first()
    thread = draft.thread


    filter = Lens(subject='/Calaveras/')
    assert filter.match(transaction)

    filter = Lens(subject='Calaveras')
    assert not filter.match(transaction)

    filter = Lens(from_addr='inboxapptest@gmail.com')
    assert filter.match(transaction)

    filter = Lens(from_addr='/inboxapp/')
    assert filter.match(transaction)

    filter = Lens(cc_addr='/Another/')
    assert filter.match(transaction)

    early_ts = calendar.timegm(thread.subjectdate.utctimetuple()) - 1
    late_ts = calendar.timegm(thread.subjectdate.utctimetuple()) + 1

    filter = Lens(started_before=late_ts)
    assert filter.match(transaction)

    filter = Lens(started_before=early_ts)
    assert not filter.match(transaction)

    filter = Lens(started_after=late_ts)
    assert not filter.match(transaction)

    filter = Lens(started_after=early_ts)
    assert filter.match(transaction)

    filter = Lens(last_message_after=early_ts)
    assert filter.match(transaction)

    filter = Lens(last_message_after=late_ts)
    assert not filter.match(transaction)

    filter = Lens(subject='/Calaveras/', any_email='Nobody')
    assert not filter.match(transaction)

    filter = Lens(subject='/Calaveras/', any_email='/inboxapp/')
    assert filter.match(transaction)

    with pytest.raises(ValueError):
        filter = Lens(subject='/*/')
