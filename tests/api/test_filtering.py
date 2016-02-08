import json
import datetime
import calendar
from sqlalchemy import desc
from inbox.models import Message, Thread, Namespace, Block, Category
from inbox.util.misc import dt_to_timestamp
from tests.util.base import (test_client, add_fake_message,
                             add_fake_thread)
from tests.api.base import api_client

__all__ = ['api_client', 'test_client']


def test_filtering(db, api_client, default_namespace):
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

    results = api_client.get_data('/threads?thread_id={}'
                                  .format(thread.public_id))
    assert len(results) == 1

    results = api_client.get_data('/messages?thread_id={}'
                                  .format(thread.public_id))
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
                                  .format(t_start - 1))
    assert len(results) == 1

    results = api_client.get_data('/messages?started_after={}'
                                  .format(t_start - 1))
    assert len(results) == 1

    results = api_client.get_data('/messages?last_message_before={}&limit=1'
                                  .format(t_lastmsg + 1))
    assert len(results) == 1

    results = api_client.get_data('/threads?last_message_before={}&limit=1'
                                  .format(t_lastmsg + 1))
    assert len(results) == 1

    results = api_client.get_data('/threads?in=inbox&limit=1')
    assert len(results) == 1

    results = api_client.get_data('/messages?in=inbox&limit=1')
    assert len(results) == 1

    results = api_client.get_data('/messages?in=banana%20rama')
    assert len(results) == 0

    results = api_client.get_data('/threads?subject={}'.format(subject))
    assert len(results) == 1

    results = api_client.get_data('/messages?subject={}'.format(subject))
    assert len(results) == 1

    results = api_client.get_data('/threads?unread={}'.format(unread))
    assert len(results) == 1

    results = api_client.get_data('/messages?unread={}'.format((not unread)))
    assert len(results) == 0

    results = api_client.get_data('/threads?starred={}'.format((not starred)))
    assert len(results) == 0

    results = api_client.get_data('/messages?starred={}'.format(starred))
    assert len(results) == 1

    for _ in range(3):
        add_fake_message(db.session, default_namespace.id,
                         to_addr=[('', 'inboxapptest@gmail.com')],
                         thread=add_fake_thread(db.session,
                                                default_namespace.id))

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

    results = api_client.get_data('/threads?view=count')

    assert results['count'] == 4

    results = api_client.get_data('/threads?view=ids&to={}&limit=3'.
                                  format('inboxapptest@gmail.com', 3))

    assert len(results) == 3
    assert all(isinstance(r, basestring)
               for r in results), "Returns a list of string"


def test_query_target(db, api_client, thread, default_namespace):
    cat = Category(namespace_id=default_namespace.id,
                   name='inbox', display_name='Inbox', type_='label')
    for _ in range(3):
        message = add_fake_message(db.session, default_namespace.id, thread,
                                   to_addr=[('Bob', 'bob@foocorp.com')],
                                   from_addr=[('Alice', 'alice@foocorp.com')],
                                   subject='some subject')
        message.categories.add(cat)
    db.session.commit()

    results = api_client.get_data('/messages?in=inbox')
    assert len(results) == 3

    count = api_client.get_data('/messages?in=inbox&view=count')
    assert count['count'] == 3


def test_ordering(api_client, db, default_namespace):
    for i in range(3):
        thr = add_fake_thread(db.session, default_namespace.id)
        received_date = (datetime.datetime.utcnow() +
                         datetime.timedelta(seconds=22 * (i + 1)))
        add_fake_message(db.session, default_namespace.id,
                         thr, received_date=received_date)
    ordered_results = api_client.get_data('/messages')
    ordered_dates = [result['date'] for result in ordered_results]
    assert ordered_dates == sorted(ordered_dates, reverse=True)

    ordered_results = api_client.get_data('/messages?limit=3')
    expected_public_ids = [
        public_id for public_id, in
        db.session.query(Message.public_id).
        filter(Message.namespace_id == default_namespace.id).
        order_by(desc(Message.received_date)).limit(3)]
    assert expected_public_ids == [r['id'] for r in ordered_results]


def test_strict_argument_parsing(api_client):
    r = api_client.get_raw('/threads?foo=bar')
    assert r.status_code == 400


def test_distinct_results(api_client, db, default_namespace):
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


def test_namespace_limiting(db, api_client, default_namespace):
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
        r = api_client.get_data('/threads?subject={}'.format(subject))
        assert len(r) == 1

        r = api_client.get_data('/messages?subject={}'.format(subject))
        assert len(r) == 1

        r = api_client.get_data('/files?filename={}'.format(subject))
        assert len(r) == 1
