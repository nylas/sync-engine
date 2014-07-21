import pytest
import calendar

from sqlalchemy import desc

from tests.util.base import config, api_client
config()

from inbox.models import (Lens, Transaction, Message)

NAMESPACE_ID = 1


def test_lens_tx(api_client, db):
    api_client.post_data('/drafts/', {
        'subject': 'Calaveras Dome / Hammer Dome',
        'to': [{'name': 'Somebody', 'email': 'somebody@example.com'}],
        'cc': [{'name': 'Another Person', 'email': 'another@example.com'}]
    })

    transaction = db.session.query(Transaction). \
        filter(Transaction.table_name == 'message'). \
        order_by(desc(Transaction.id)).first()

    draft = db.session.query(Message).filter(Message.is_draft).\
        order_by(desc(Message.id)).first()
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
