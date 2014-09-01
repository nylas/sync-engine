import datetime
import calendar
from inbox.models import Message, Thread
from inbox.contacts.process_mail import update_contacts_from_message
from inbox.util.misc import dt_to_timestamp
from tests.util.base import api_client

__all__ = ['api_client']

NAMESPACE_ID = 1


def test_filtering(db, api_client):
    message = db.session.query(Message).filter_by(id=2).one()
    thread = message.thread
    t_start = dt_to_timestamp(thread.subjectdate)
    t_lastmsg = dt_to_timestamp(thread.recentdate)

    subject = message.subject
    to_addr = message.to_addr[0][1]
    from_addr = message.from_addr[0][1]
    received_date = message.received_date

    results = api_client.get_data('/threads?thread_id={}'
                                  .format('e6z26rjrxs2gu8at6gsa8svr1'))
    assert len(results) == 1

    results = api_client.get_data('/messages?thread_id={}'
                                  .format('e6z26rjrxs2gu8at6gsa8svr1'))
    assert len(results) == 1

    results = api_client.get_data('/threads?cc={}'
                                  .format(message.cc_addr))
    assert len(results) == 0

    results = api_client.get_data('/messages?cc={}'
                                  .format(message.cc_addr))
    assert len(results) == 0

    results = api_client.get_data('/threads?bcc={}'
                                  .format(message.bcc_addr))
    assert len(results) == 0

    results = api_client.get_data('/messages?bcc={}'
                                  .format(message.bcc_addr))
    assert len(results) == 0

    results = api_client.get_data('/threads?filename=test')
    assert len(results) == 0

    results = api_client.get_data('/messages?filename=test')
    assert len(results) == 0

    results = api_client.get_data('/threads?started_after={}'
                                  .format(t_start-1))
    assert len(results) == 1

    results = api_client.get_data('/messages?started_after={}'
                                  .format(t_start-1))
    assert len(results) == 1

    results = api_client.get_data('/messages?last_message_before={}&limit=1'
                                  .format(t_lastmsg+1))
    assert len(results) == 1

    results = api_client.get_data('/threads?last_message_before={}&limit=1'
                                  .format(t_lastmsg+1))
    assert len(results) == 1

    results = api_client.get_data('/threads?tag={}&limit=1'
                                  .format('inbox'))
    assert len(results) == 1

    results = api_client.get_data('/messages?tag={}&limit=1'
                                  .format('inbox'))
    assert len(results) == 1

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
    assert len(results) == 1

    results = api_client.get_data('/threads?from={}&to={}'.
                                  format(from_addr, to_addr))
    assert len(results) == 1

    results = api_client.get_data('/messages?to={}&limit={}&offset={}'.
                                  format('inboxapptest@gmail.com', 2, 1))
    assert len(results) == 2

    results = api_client.get_data('/threads?to={}&limit={}'.
                                  format('inboxapptest@gmail.com', 3))
    assert len(results) == 3


def test_ordering(api_client):
    ordered_results = api_client.get_data('/messages')
    ordered_dates = [result['date'] for result in ordered_results]
    assert ordered_dates == sorted(ordered_dates, reverse=True)


def test_strict_argument_parsing(api_client):
    r = api_client.client.get(api_client.full_path('/threads?foo=bar'))
    assert r.status_code == 400


def add_fake_message(account_id, thread, to_email, received_date,
                     db_session):
    """ One-off helper function to add 'fake' messages to the datastore."""
    m = Message()
    m.from_addr = [('', to_email)]
    m.received_date = received_date
    m.size = 0
    m.sanitized_body = ''
    m.snippet = ''
    m.thread = thread
    update_contacts_from_message(db_session, m, account_id)
    db_session.add(m)
    db_session.commit()


def test_distinct_results(api_client, db):
    """Test that limit and offset parameters work correctly when joining on
    multiple matching messages per thread."""
    # Create a thread with multiple messages on it.
    first_thread = db.session.query(Thread).filter(
        Thread.namespace_id == NAMESPACE_ID).get(1)
    add_fake_message(NAMESPACE_ID, first_thread, 'hello@example.com',
                     datetime.datetime.utcnow(), db.session)
    add_fake_message(NAMESPACE_ID, first_thread, 'hello@example.com',
                     datetime.datetime.utcnow(), db.session)

    # Now create another thread with the same participants
    older_date = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    second_thread = db.session.query(Thread).filter(
        Thread.namespace_id == NAMESPACE_ID).get(2)
    add_fake_message(NAMESPACE_ID, second_thread, 'hello@example.com',
                     older_date, db.session)
    add_fake_message(NAMESPACE_ID, second_thread, 'hello@example.com',
                     older_date, db.session)

    filtered_results = api_client.get_data('/threads?from=hello@example.com'
                                           '&limit=1&offset=0')
    assert len(filtered_results) == 1
    assert filtered_results[0]['id'] == first_thread.public_id

    filtered_results = api_client.get_data('/threads?from=hello@example.com'
                                           '&limit=1&offset=1')
    assert len(filtered_results) == 1
    assert filtered_results[0]['id'] == second_thread.public_id

    filtered_results = api_client.get_data('/threads?from=hello@example.com'
                                           '&limit=2&offset=0')
    assert len(filtered_results) == 2

    filtered_results = api_client.get_data('/threads?from=hello@example.com'
                                           '&limit=2&offset=1')
    assert len(filtered_results) == 1
