import json
import datetime
import pytest
from tests.util.base import (add_fake_message, default_account,
                             add_fake_thread, db)
from tests.api.base import api_client

__all__ = ['db', 'api_client', 'default_account']


@pytest.fixture(params=['/threads', '/threads2'])
def threads_endpoint(request):
    return request.param


def test_thread_received_recent_date(db, api_client, threads_endpoint, default_account):
    date1 = datetime.datetime(2015, 1, 1, 0, 0, 0)
    date2 = datetime.datetime(2012, 1, 1, 0, 0, 0)

    thread1 = add_fake_thread(db.session, default_account.namespace.id)

    date_dict = dict()

    add_fake_message(db.session, default_account.namespace.id, thread1,
                     subject="Test Thread 1", received_date=date1,
                     add_sent_category=True)
    add_fake_message(db.session, default_account.namespace.id, thread1,
                     subject="Test Thread 1", received_date=date2)

    date_dict["Test Thread 1"] = date2

    thread2 = add_fake_thread(db.session, default_account.namespace.id)
    add_fake_message(db.session, default_account.namespace.id, thread2,
                     subject="Test Thread 2", received_date=date1,
                     add_sent_category=True)

    date_dict["Test Thread 2"] = date1

    resp = api_client.get_raw(threads_endpoint)
    assert resp.status_code == 200
    threads = json.loads(resp.data)

    for thread in threads:
        assert date_dict[thread['subject']] == \
            datetime.datetime.fromtimestamp(
                thread['last_message_received_timestamp'])


def test_thread_sent_recent_date(db, api_client, threads_endpoint, default_account):
    date1 = datetime.datetime(2015, 1, 1, 0, 0, 0)
    date2 = datetime.datetime(2012, 1, 1, 0, 0, 0)
    date3 = datetime.datetime(2010, 1, 1, 0, 0, 0)
    date4 = datetime.datetime(2009, 1, 1, 0, 0, 0)
    date5 = datetime.datetime(2008, 1, 1, 0, 0, 0)

    thread1 = add_fake_thread(db.session, default_account.namespace.id)

    test_subject = "test_thread_sent_recent_date"

    add_fake_message(db.session, default_account.namespace.id, thread1,
                     subject=test_subject, received_date=date1)
    add_fake_message(db.session, default_account.namespace.id, thread1,
                     subject=test_subject, received_date=date2,
                     add_sent_category=True)
    add_fake_message(db.session, default_account.namespace.id, thread1,
                     subject=test_subject, received_date=date3)
    add_fake_message(db.session, default_account.namespace.id, thread1,
                     subject=test_subject, received_date=date4,
                     add_sent_category=True)
    add_fake_message(db.session, default_account.namespace.id, thread1,
                     subject=test_subject, received_date=date5)

    resp = api_client.get_raw(threads_endpoint)
    assert resp.status_code == 200
    threads = json.loads(resp.data)

    for thread in threads:  # should only be one
        assert datetime.datetime.fromtimestamp(
            thread['last_message_sent_timestamp']) == date2
