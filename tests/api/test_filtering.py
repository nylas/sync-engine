import datetime
import calendar
from inbox.models import Message
from tests.util.base import api_client

NAMESPACE_ID = 1


def test_filtering(db, api_client):
    message = db.session.query(Message).filter_by(id=2).one()

    subject = message.subject
    to_addr = message.to_addr[0][1]
    from_addr = message.from_addr[0][1]
    received_date = message.received_date

    results = api_client.get_data('/messages?subject={}'.format(subject))
    assert len(results) == 1
    results = api_client.get_data('/threads?subject={}'.format(subject))
    assert len(results) == 1

    results = api_client.get_data('/messages?any_email={}'.
                                  format('inboxapptest@gmail.com'))
    assert len(results) > 1
    results = api_client.get_data('/threads?any_email={}'.
                                  format('inboxapptest@gmail.com'))
    assert len(results) > 1

    # Check that we canonicalize when searching.
    alternate_results = api_client.get_data('/threads?any_email={}'.
                                            format('inboxapp.test@gmail.com'))
    assert len(alternate_results) == len(results)

    results = api_client.get_data('/messages?from={}'.format(from_addr))
    assert len(results) == 1
    results = api_client.get_data('/threads?from={}'.format(from_addr))
    assert len(results) == 1

    early_time = received_date - datetime.timedelta(seconds=1)
    late_time = received_date + datetime.timedelta(seconds=1)
    early_ts = calendar.timegm(early_time.utctimetuple())
    late_ts = calendar.timegm(late_time.utctimetuple())

    results = api_client.get_data('/messages?subject={}&started_before={}'.
                                  format(subject, early_ts))
    assert len(results) == 0
    results = api_client.get_data('/threads?subject={}&started_before={}'.
                                  format(subject, early_ts))
    assert len(results) == 0

    results = api_client.get_data('/messages?subject={}&started_before={}'.
                                  format(subject, late_ts))
    assert len(results) == 1
    results = api_client.get_data('/threads?subject={}&started_before={}'.
                                  format(subject, late_ts))
    assert len(results) == 1

    results = api_client.get_data('/messages?subject={}&last_message_after={}'.
                                  format(subject, early_ts))
    assert len(results) == 1
    results = api_client.get_data('/threads?subject={}&last_message_after={}'.
                                  format(subject, early_ts))
    assert len(results) == 1

    results = api_client.get_data('/messages?subject={}&last_message_after={}'.
                                  format(subject, late_ts))
    assert len(results) == 0
    results = api_client.get_data('/threads?subject={}&last_message_after={}'.
                                  format(subject, late_ts))
    assert len(results) == 0

    results = api_client.get_data('/messages?subject={}&started_before={}'.
                                  format(subject, early_ts))
    assert len(results) == 0
    results = api_client.get_data('/threads?subject={}&started_before={}'.
                                  format(subject, early_ts))
    assert len(results) == 0

    results = api_client.get_data('/messages?subject={}&started_before={}'.
                                  format(subject, late_ts))
    assert len(results) == 1
    results = api_client.get_data('/threads?subject={}&started_before={}'.
                                  format(subject, late_ts))
    assert len(results) == 1

    results = api_client.get_data('/messages?from={}&to={}'.
                                  format(from_addr, to_addr))
    results = api_client.get_data('/threads?from={}&to={}'.
                                  format(from_addr, to_addr))
    assert len(results) == 1
    assert len(results) == 1

    results = api_client.get_data('/messages?to={}&limit={}'.
                                  format('inboxapptest@gmail.com', 3))
    results = api_client.get_data('/threads?to={}&limit={}'.
                                  format('inboxapptest@gmail.com', 3))
    assert len(results) == 3
    assert len(results) == 3


def test_ordering(api_client):
    ordered_results = api_client.get_data('/messages')
    ordered_dates = [result['date'] for result in ordered_results]
    assert ordered_dates == sorted(ordered_dates, reverse=True)
