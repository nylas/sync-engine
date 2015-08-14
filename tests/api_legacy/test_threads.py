import json
import datetime
from tests.util.base import (add_fake_message, default_account,
                             add_fake_thread, db)
from tests.api_legacy.base import api_client

__all__ = ['db', 'api_client', 'default_account']


def test_thread_received_recent_date(db, api_client, default_account):
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

    resp = api_client.client.get(api_client.full_path('/threads/'))
    assert resp.status_code == 200
    threads = json.loads(resp.data)

    for thread in threads:
        assert date_dict[thread['subject']] == \
            datetime.datetime.fromtimestamp(
                thread['last_message_received_timestamp'])
