import json
import datetime
import calendar
from sqlalchemy import desc
from inbox.models import Message, Thread, Namespace, Block
from inbox.util.misc import dt_to_timestamp
from tests.util.base import api_client, test_client, add_fake_message

__all__ = ['api_client', 'test_client']

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

    results = api_client.get_data('/threads?view=count')

    assert results['count'] == 16

    results = api_client.get_data('/threads?view=ids&to={}&limit=3'.
                                  format('inboxapptest@gmail.com', 3))

    assert len(results) == 3
    assert all(isinstance(r, basestring)
               for r in results), "Returns a list of string"


def test_ordering(api_client, db):
    ordered_results = api_client.get_data('/messages')
    ordered_dates = [result['date'] for result in ordered_results]
    assert ordered_dates == sorted(ordered_dates, reverse=True)

    ordered_results = api_client.get_data('/messages?limit=3')
    expected_public_ids = [public_id for public_id, in
                           db.session.query(Message.public_id).
                           order_by(desc(Message.received_date)).limit(3)]
    assert expected_public_ids == [r['id'] for r in ordered_results]


def test_strict_argument_parsing(api_client):
    r = api_client.client.get(api_client.full_path('/threads?foo=bar'))
    assert r.status_code == 400


def test_distinct_results(api_client, db):
    """Test that limit and offset parameters work correctly when joining on
    multiple matching messages per thread."""
    # Create a thread with multiple messages on it.
    first_thread = db.session.query(Thread).filter(
        Thread.namespace_id == NAMESPACE_ID)[0]
    add_fake_message(db.session, NAMESPACE_ID, first_thread,
                     from_addr=[('', 'hello@example.com')],
                     received_date=datetime.datetime.utcnow())
    add_fake_message(db.session, NAMESPACE_ID, first_thread,
                     from_addr=[('', 'hello@example.com')],
                     received_date=datetime.datetime.utcnow())

    # Now create another thread with the same participants
    older_date = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    second_thread = db.session.query(Thread).filter(
        Thread.namespace_id == NAMESPACE_ID)[1]
    add_fake_message(db.session, NAMESPACE_ID, second_thread,
                     from_addr=[('', 'hello@example.com')],
                     received_date=older_date)
    add_fake_message(db.session, NAMESPACE_ID, second_thread,
                     from_addr=[('', 'hello@example.com')],
                     received_date=older_date)

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


def test_filtering_namespaces(db, test_client):
    all_namespaces = json.loads(test_client.get('/n/').data)
    email = all_namespaces[0]['email_address']

    no_namespaces = json.loads(test_client.get('/n/?limit=0').data)
    assert no_namespaces == []

    all_namespaces = json.loads(test_client.get('/n/?limit=1').data)
    assert len(all_namespaces) == 1

    some_namespaces = json.loads(test_client.get('/n/?offset=1').data)
    assert len(some_namespaces) == len(all_namespaces) - 1

    filter_ = '?email_address={}'.format(email)
    namespaces = json.loads(test_client.get('/n/' + filter_).data)
    assert namespaces[0]['email_address'] == email

    filter_ = '?email_address=unknown@email.com'
    namespaces = json.loads(test_client.get('/n/' + filter_).data)
    assert len(namespaces) == 0


def test_namespace_limiting(db, test_client):
    dt = datetime.datetime.utcnow()
    subject = dt.isoformat()
    db.session.add(Namespace())
    db.session.commit()
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
        r = json.loads(test_client.get('/n/{}/threads?subject={}'.
                                       format(ns.public_id, subject)).data)
        assert len(r) == 1

        r = json.loads(test_client.get('/n/{}/messages?subject={}'.
                                       format(ns.public_id, subject)).data)
        assert len(r) == 1

        r = json.loads(test_client.get('/n/{}/files?filename={}'.
                                       format(ns.public_id, subject)).data)
        assert len(r) == 1
