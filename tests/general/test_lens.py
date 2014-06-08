import pytest
import datetime
import calendar

from tests.data.messages.message import (subject, delivered_to, sender,
                                         to_addr, from_addr, received_date)
from tests.util.base import config
config()

from inbox.models.tables.base import register_backends, Lens
register_backends()

NAMESPACE_ID = 1


def test_lens_db_filter(db):
    filter = Lens(namespace_id=NAMESPACE_ID,
                  subject=subject)
    assert filter.message_query(db.session).count() == 1
    assert filter.thread_query(db.session).count() == 1

    filter = Lens(namespace_id=NAMESPACE_ID,
                  any_email=delivered_to)
    assert filter.message_query(db.session).count() > 1
    assert filter.thread_query(db.session).count() > 1

    filter = Lens(namespace_id=NAMESPACE_ID,
                  any_email=sender)
    assert filter.message_query(db.session).count() == 1
    assert filter.thread_query(db.session).count() == 1

    early_time = received_date - datetime.timedelta(hours=1)
    late_time = received_date + datetime.timedelta(hours=1)
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


@pytest.fixture
def message_data():
    return {
        "sender_addr": [],
        "thread_id": 36,
        "bcc_addr": [],
        "cc_addr": [["Michael Levin", "risujin@gmail.com"],
                    ["Daniel Gerber", "daniel.l.gerber@gmail.com"],
                    ["Victor Li", "vintorli@gmail.com"],
                    ["Robin Young", "robinyoung3@gmail.com"],
                    ["Andreas Binnewies", "abinnewies@gmail.com"],
                    ["suman chakravartula", "schakrava@gmail.com"],
                    ["Russell Cohen", "russell.r.cohen@gmail.com"],
                    ["Andrew Townley", "townley.andrew@gmail.com"]],
        "sanitized_body": "<html><body><div dir=\"ltr\">WOOHOO! Let's do it!</div><div class=\"gmail_extra\"></div></body></html>",
        "id": 78,
        "subject": "Calaveras Dome / Hammer Dome",
        "g_msgid": 1466116539240163181,
        "from_addr": [["Eben Freeman", "freemaneben@gmail.com"]],
        "g_thrid": 1465956332002552803,
        "inbox_uid": None,
        "snippet": "WOOHOO! Let's do it!",
        "message_id_header": "<CANtwz5jndG6PXL15wb+CTdnNpVrbPftFRmSsfqxn2XwBo7KqFA@mail.gmail.com>",
        "received_date": datetime.datetime(2014, 4, 22, 20, 14, 48),
        "size": 4621,
        "type": "message",
        "to_addr": [["Naren", "narenst@gmail.com"]],
        "mailing_list_headers": {
            "List-Id": None, "List-Post": None, "List-Owner": None,
            "List-Subscribe": None, "List-Unsubscribe": None, "List-Archive":
            None, "List-Help": None},
        "in_reply_to": "<CALn-WSKBm06t6ZEKPHMSj2a2RKG3S9_-muH7eCQHmDcDq6vH_w@mail.gmail.com>",
        "is_draft": False,
        "data_sha256": "b30f46fc70536e5268f025a2faf378c24d727c778143025f6b5b775945bbb4fc",
        "reply_to": [],
        "blocks": [
            {"g_index": 0, "g_id": 1466116539240163181, "filename": None,
             "content_type": None, "content_disposition": None, "size": 1129},
            {"g_index": 0, "g_id": 1466116539240163181, "filename":
             None, "content_type": None, "content_disposition": None,
             "size": 1129},
            {"g_index": 1, "g_id": 1466116539240163181, "filename":
             None, "content_type": "text/plain", "content_disposition":
             None, "size": 913},
            {"g_index": 1, "g_id": 1466116539240163181, "filename":
             None, "content_type": "text/plain", "content_disposition":
             None, "size": 913},
            {"g_index": 2, "g_id": 1466116539240163181, "filename":
             None, "content_type": "text/html", "content_disposition":
             None, "size": 2234},
            {"g_index": 2, "g_id": 1466116539240163181, "filename":
             None, "content_type": "text/html", "content_disposition":
             None, "size": 2234}
        ],
        "thread": {
            "recent_date": datetime.datetime(2014, 4, 29, 23, 55, 15),
            "subject_date": datetime.datetime(2014, 4, 22, 20, 14, 48),
            "object": "thread",
            "messages": ["1otlne5eyu5rjzrh90qs501uh"],
            "participants": None,
            "ns": "8h4i406v9pymwdfn5ipglkluc",
            "id": "2fk859tx6jarr8uxgg84fbw0z",
            "subject": "Calaveras Dome / Hammer Dome"
        },
        "namespace_public_id": "8h4i406v9pymwdfn5ipglkluc"
    }


def test_lens_tx(message_data):
    filter = Lens(subject='/Calaveras/')
    assert filter.match(message_data)

    filter = Lens(subject='Calaveras')
    assert not filter.match(message_data)

    filter = Lens(from_addr='freemaneben@gmail.com')
    assert filter.match(message_data)

    filter = Lens(from_addr='/freemaneben/')
    assert filter.match(message_data)

    filter = Lens(cc_addr='/Daniel/')
    assert filter.match(message_data)

    early_ts = calendar.timegm(
        datetime.datetime(2014, 04, 22, 20, 10, 00).utctimetuple())
    late_ts = calendar.timegm(
        datetime.datetime(2014, 04, 30, 00, 00, 00).utctimetuple())

    filter = Lens(started_before=late_ts)
    assert filter.match(message_data)

    filter = Lens(started_before=early_ts)
    assert not filter.match(message_data)

    filter = Lens(started_after=late_ts)
    assert not filter.match(message_data)

    filter = Lens(started_after=early_ts)
    assert filter.match(message_data)

    filter = Lens(last_message_after=early_ts)
    assert filter.match(message_data)

    filter = Lens(last_message_after=late_ts)
    assert not filter.match(message_data)

    filter = Lens(subject='/Calaveras/', any_email='Nobody')
    assert not filter.match(message_data)

    filter = Lens(subject='/Calaveras/', any_email='/freemaneben/')
    assert filter.match(message_data)

    thread_public_id = '2fk859tx6jarr8uxgg84fbw0z'

    filter = Lens(thread_public_id=thread_public_id)
    assert filter.match(message_data)

    with pytest.raises(ValueError):
        filter = Lens(subject='/*/')
