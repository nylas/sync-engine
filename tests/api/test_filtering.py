import json
import datetime
import calendar
from sqlalchemy import desc
import pytest
from inbox.models import Message, Thread, Namespace, Block, Category
from inbox.util.misc import dt_to_timestamp
from tests.util.base import (test_client, add_fake_message,
                             add_fake_thread)
from tests.api.base import api_client

__all__ = ['api_client', 'test_client']


@pytest.fixture(params=['/messages', '/messages2'])
def messages_endpoint(request):
    return request.param


@pytest.fixture(params=['/threads', '/threads2'])
def threads_endpoint(request):
    return request.param


def test_filtering(db, api_client, threads_endpoint, messages_endpoint, default_namespace):
    thread = add_fake_thread(db.session, default_namespace.id)
    message = add_fake_message(db.session, default_namespace.id, thread,
                               to_addr=[('Bob', 'bob@foocorp.com')],
                               from_addr=[('Alice', 'alice@foocorp.com')],
                               subject='some subject')
    message.categories.add(
        Category(namespace_id=message.namespace_id,
                 name='inbox', display_name='Inbox', type_='label'))
    thread.subject = message.subject
    db.session.commit()

    t_start = dt_to_timestamp(thread.subjectdate)
    t_lastmsg = dt_to_timestamp(thread.recentdate)
    subject = message.subject
    to_addr = message.to_addr[0][1]
    from_addr = message.from_addr[0][1]
    received_date = message.received_date
    unread = not message.is_read
    starred = message.is_starred

    results = api_client.get_data(threads_endpoint + '?thread_id={}'
                                  .format(thread.public_id))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?thread_id={}'
                                  .format(thread.public_id))
    assert len(results) == 1

    results = api_client.get_data(threads_endpoint + '?cc={}'
                                  .format(message.cc_addr))
    assert len(results) == 0

    results = api_client.get_data(messages_endpoint + '?cc={}'
                                  .format(message.cc_addr))
    assert len(results) == 0

    results = api_client.get_data(threads_endpoint + '?bcc={}'
                                  .format(message.bcc_addr))
    assert len(results) == 0

    results = api_client.get_data(messages_endpoint + '?bcc={}'
                                  .format(message.bcc_addr))
    assert len(results) == 0

    results = api_client.get_data(threads_endpoint + '?filename=test')
    assert len(results) == 0

    results = api_client.get_data(messages_endpoint + '?filename=test')
    assert len(results) == 0

    results = api_client.get_data(threads_endpoint + '?started_after={}'
                                  .format(t_start - 1))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?started_after={}'
                                  .format(t_start - 1))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?last_message_before={}&limit=1'
                                  .format(t_lastmsg + 1))
    assert len(results) == 1

    results = api_client.get_data(threads_endpoint + '?last_message_before={}&limit=1'
                                  .format(t_lastmsg + 1))
    assert len(results) == 1

    results = api_client.get_data(threads_endpoint + '?in=inbox&limit=1')
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?in=inbox&limit=1')
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?in=banana%20rama')
    assert len(results) == 0

    results = api_client.get_data(threads_endpoint + '?subject={}'.format(subject))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?subject={}'.format(subject))
    assert len(results) == 1

    results = api_client.get_data(threads_endpoint + '?unread={}'.format(unread))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?unread={}'.format((not unread)))
    assert len(results) == 0

    results = api_client.get_data(threads_endpoint + '?starred={}'.format((not starred)))
    assert len(results) == 0

    results = api_client.get_data(messages_endpoint + '?starred={}'.format(starred))
    assert len(results) == 1

    for _ in range(3):
        add_fake_message(db.session, default_namespace.id,
                         to_addr=[('', 'inboxapptest@gmail.com')],
                         thread=add_fake_thread(db.session,
                                                default_namespace.id))

    results = api_client.get_data(messages_endpoint + '?any_email={}'.
                                  format('inboxapptest@gmail.com'))
    assert len(results) > 1

    # Test multiple any_email params
    multiple_results = api_client.get_data(messages_endpoint + '?any_email={},{},{}'.
                                  format('inboxapptest@gmail.com',
                                         'bob@foocorp.com',
                                         'unused@gmail.com'))
    assert len(multiple_results) > len(results)


    # Check that we canonicalize when searching.
    alternate_results = api_client.get_data(threads_endpoint + '?any_email={}'.
                                            format('inboxapp.test@gmail.com'))
    assert len(alternate_results) == len(results)

    results = api_client.get_data(messages_endpoint + '?from={}'.format(from_addr))
    assert len(results) == 1
    results = api_client.get_data(threads_endpoint + '?from={}'.format(from_addr))
    assert len(results) == 1

    early_time = received_date - datetime.timedelta(seconds=1)
    late_time = received_date + datetime.timedelta(seconds=1)
    early_ts = calendar.timegm(early_time.utctimetuple())
    late_ts = calendar.timegm(late_time.utctimetuple())

    results = api_client.get_data(messages_endpoint + '?subject={}&started_before={}'.
                                  format(subject, early_ts))
    assert len(results) == 0
    results = api_client.get_data(threads_endpoint + '?subject={}&started_before={}'.
                                  format(subject, early_ts))
    assert len(results) == 0

    results = api_client.get_data(messages_endpoint + '?subject={}&started_before={}'.
                                  format(subject, late_ts))
    assert len(results) == 1
    results = api_client.get_data(threads_endpoint + '?subject={}&started_before={}'.
                                  format(subject, late_ts))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?subject={}&last_message_after={}'.
                                  format(subject, early_ts))
    assert len(results) == 1
    results = api_client.get_data(threads_endpoint + '?subject={}&last_message_after={}'.
                                  format(subject, early_ts))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?subject={}&last_message_after={}'.
                                  format(subject, late_ts))
    assert len(results) == 0
    results = api_client.get_data(threads_endpoint + '?subject={}&last_message_after={}'.
                                  format(subject, late_ts))
    assert len(results) == 0

    results = api_client.get_data(messages_endpoint + '?subject={}&started_before={}'.
                                  format(subject, early_ts))
    assert len(results) == 0
    results = api_client.get_data(threads_endpoint + '?subject={}&started_before={}'.
                                  format(subject, early_ts))
    assert len(results) == 0

    results = api_client.get_data(messages_endpoint + '?subject={}&started_before={}'.
                                  format(subject, late_ts))
    assert len(results) == 1
    results = api_client.get_data(threads_endpoint + '?subject={}&started_before={}'.
                                  format(subject, late_ts))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?from={}&to={}'.
                                  format(from_addr, to_addr))
    assert len(results) == 1

    results = api_client.get_data(threads_endpoint + '?from={}&to={}'.
                                  format(from_addr, to_addr))
    assert len(results) == 1

    results = api_client.get_data(messages_endpoint + '?to={}&limit={}&offset={}'.
                                  format('inboxapptest@gmail.com', 2, 1))
    assert len(results) == 2

    results = api_client.get_data(threads_endpoint + '?to={}&limit={}'.
                                  format('inboxapptest@gmail.com', 3))
    assert len(results) == 3

    results = api_client.get_data(threads_endpoint + '?view=count')

    assert results['count'] == 4

    results = api_client.get_data(threads_endpoint + '?view=ids&to={}&limit=3'.
                                  format('inboxapptest@gmail.com', 3))

    assert len(results) == 3
    assert all(isinstance(r, basestring)
               for r in results), "Returns a list of string"


def test_query_target(db, api_client, messages_endpoint, thread, default_namespace):
    cat = Category(namespace_id=default_namespace.id,
                   name='inbox', display_name='Inbox', type_='label')
    for _ in range(3):
        message = add_fake_message(db.session, default_namespace.id, thread,
                                   to_addr=[('Bob', 'bob@foocorp.com')],
                                   from_addr=[('Alice', 'alice@foocorp.com')],
                                   subject='some subject')
        message.categories.add(cat)
    db.session.commit()

    results = api_client.get_data(messages_endpoint + '?in=inbox')
    assert len(results) == 3

    count = api_client.get_data(messages_endpoint + '?in=inbox&view=count')
    assert count['count'] == 3


def test_ordering(api_client, messages_endpoint, db, default_namespace):
    for i in range(3):
        thr = add_fake_thread(db.session, default_namespace.id)
        received_date = (datetime.datetime.utcnow() +
                         datetime.timedelta(seconds=22 * (i + 1)))
        add_fake_message(db.session, default_namespace.id,
                         thr, received_date=received_date)
    ordered_results = api_client.get_data(messages_endpoint)
    ordered_dates = [result['date'] for result in ordered_results]
    assert ordered_dates == sorted(ordered_dates, reverse=True)

    ordered_results = api_client.get_data(messages_endpoint + '?limit=3')
    expected_public_ids = [
        public_id for public_id, in
        db.session.query(Message.public_id).
        filter(Message.namespace_id == default_namespace.id).
        order_by(desc(Message.received_date)).limit(3)]
    assert expected_public_ids == [r['id'] for r in ordered_results]


def test_strict_argument_parsing(api_client, threads_endpoint):
    r = api_client.get_raw(threads_endpoint + '?foo=bar')
    assert r.status_code == 400


def test_distinct_results(api_client, threads_endpoint, db, default_namespace):
    """Test that limit and offset parameters work correctly when joining on
    multiple matching messages per thread."""
    # Create a thread with multiple messages on it.
    first_thread = add_fake_thread(db.session, default_namespace.id)
    add_fake_message(db.session, default_namespace.id, first_thread,
                     from_addr=[('', 'hello@example.com')],
                     received_date=datetime.datetime.utcnow())
    add_fake_message(db.session, default_namespace.id, first_thread,
                     from_addr=[('', 'hello@example.com')],
                     received_date=datetime.datetime.utcnow())

    # Now create another thread with the same participants
    older_date = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    second_thread = add_fake_thread(db.session, default_namespace.id)
    add_fake_message(db.session, default_namespace.id, second_thread,
                     from_addr=[('', 'hello@example.com')],
                     received_date=older_date)
    add_fake_message(db.session, default_namespace.id, second_thread,
                     from_addr=[('', 'hello@example.com')],
                     received_date=older_date)
    second_thread.recentdate = older_date
    db.session.commit()

    filtered_results = api_client.get_data(threads_endpoint + '?from=hello@example.com'
                                           '&limit=1&offset=0')
    assert len(filtered_results) == 1
    assert filtered_results[0]['id'] == first_thread.public_id

    filtered_results = api_client.get_data(threads_endpoint + '?from=hello@example.com'
                                           '&limit=1&offset=1')
    assert len(filtered_results) == 1
    assert filtered_results[0]['id'] == second_thread.public_id

    filtered_results = api_client.get_data(threads_endpoint + '?from=hello@example.com'
                                           '&limit=2&offset=0')
    assert len(filtered_results) == 2

    filtered_results = api_client.get_data(threads_endpoint + '?from=hello@example.com'
                                           '&limit=2&offset=1')
    assert len(filtered_results) == 1


def test_filtering_accounts(db, test_client):
    all_accounts = json.loads(test_client.get('/accounts/?limit=100').data)
    email = all_accounts[0]['email_address']

    some_accounts = json.loads(test_client.get('/accounts/?offset=1&limit=99').data)
    assert len(some_accounts) == len(all_accounts) - 1

    no_all_accounts = json.loads(test_client.get('/accounts/?limit=0').data)
    assert no_all_accounts == []

    all_accounts = json.loads(test_client.get('/accounts/?limit=1').data)
    assert len(all_accounts) == 1

    filter_ = '?email_address={}'.format(email)
    all_accounts = json.loads(test_client.get('/accounts/' + filter_).data)
    assert all_accounts[0]['email_address'] == email

    filter_ = '?email_address=unknown@email.com'
    accounts = json.loads(test_client.get('/accounts/' + filter_).data)
    assert len(accounts) == 0


def test_namespace_limiting(db, api_client, threads_endpoint, messages_endpoint, default_namespace):
    dt = datetime.datetime.utcnow()
    subject = dt.isoformat()
    namespaces = db.session.query(Namespace).all()
    assert len(namespaces) > 1
    for ns in namespaces:
        thread = Thread(namespace=ns, subjectdate=dt, recentdate=dt,
                        subject=subject)
        add_fake_message(db.session, ns.id, thread, received_date=dt,
                         subject=subject)
        db.session.add(Block(namespace=ns, filename=subject))
    db.session.commit()

    for ns in namespaces:
        r = api_client.get_data(threads_endpoint + '?subject={}'.format(subject))
        assert len(r) == 1

        r = api_client.get_data(messages_endpoint + '?subject={}'.format(subject))
        assert len(r) == 1

        r = api_client.get_data('/files?filename={}'.format(subject))
        assert len(r) == 1
