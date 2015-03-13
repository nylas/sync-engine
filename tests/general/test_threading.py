# -*- coding: utf-8 -*-
import pytest
from datetime import datetime
from inbox.util.threading import thread_messages, fetch_corresponding_thread
from inbox.util.misc import cleanup_subject
from collections import namedtuple
from tests.util.base import (add_fake_message, add_fake_thread,
                             add_fake_imapuid)


def test_message_cleanup():
    assert cleanup_subject("Re: Birthday") == "Birthday"
    assert cleanup_subject("Re:Birthday") == "Birthday"
    assert cleanup_subject("Re:FWD:   Birthday") == "Birthday"
    assert (cleanup_subject("Re: RE: Alors, comment ça s'est passé ?")
                == "Alors, comment ça s'est passé ?")
    assert cleanup_subject("Re: FWD:FWD: Re:La chaise") == "La chaise"

    assert cleanup_subject("Aw: über cool") == "über cool"
    assert cleanup_subject("Aw:Re:wienerschnitzel") == "wienerschnitzel"
    assert cleanup_subject("Aw: wienerschnitzel") == "wienerschnitzel"
    assert cleanup_subject("aw: wg:wienerschnitzel") == "wienerschnitzel"


def test_threading():
    Message = namedtuple('Message', ['message_id_header', 'references',
                                     'received_date'])
    messages = [Message("aaa_header", [], datetime(1999, 1, 23)),
                Message("bbb_header", ["aaa_header"], datetime(2000, 12, 23)),
                Message("ccc_header", ["bbb_header"], datetime(2000, 12, 24))]

    assert thread_messages(messages) == messages

    messages2 = [Message("aaa_header", [], datetime(1999, 1, 23)),
                 Message("bbb_header", ["aaa_header"], datetime(2000, 12, 23)),
                 Message("ccc_header", ["aaa_header"], datetime(2000, 12, 24)),
                 Message("ddd_header", ["bbb_header"], datetime(2000, 12, 25))]

    assert thread_messages(messages2) == messages2

    messages3 = [Message("aaa_header", [], datetime(1999, 1, 23)),
                 Message("bbb_header", ["aaa_header"], datetime(2000, 12, 23)),
                 Message("ccc_header", [], datetime(2000, 12, 23)),
                 Message("ddd_header", ["bbb_header"], datetime(2000, 12, 23))]

    assert thread_messages(messages3) == messages3


def test_basic_message_grouping(db, default_namespace):
    first_thread = add_fake_thread(db.session, default_namespace.id)
    first_thread.subject = 'Some kind of test'

    msg1 = add_fake_message(db.session, default_namespace.id, first_thread)
    msg1.subject = 'Some kind of test'
    msg1.from_addr = [('Karim Hamidou', 'karim@nilas.com')]
    msg1.to_addr =   [('Eben Freeman', 'emfree@nilas.com')]
    msg1.bcc_addr =  [('Some person', 'person@nilas.com')]

    msg2 = add_fake_message(db.session, default_namespace.id, thread=None)
    msg2.subject = 'Re: Some kind of test'
    msg2.from_addr = [('Some random dude', 'random@pobox.com')]
    msg2.to_addr =   [('Karim Hamidou', 'karim@nilas.com')]

    matched_thread = fetch_corresponding_thread(db.session,
                                                default_namespace.id, msg2)
    assert matched_thread is None, "the algo shouldn't thread different convos"

    msg3 = add_fake_message(db.session, default_namespace.id, thread=None)
    msg3.subject = 'Re: Some kind of test'
    msg3.from_addr = [('Eben Freeman', 'emfree@nilas.com')]
    msg3.to_addr =   [('Karim Hamidou', 'karim@nilas.com')]

    matched_thread = fetch_corresponding_thread(db.session, default_namespace.id, msg3)
    assert matched_thread is first_thread, "Should match on participants"


def test_self_send(db, default_namespace):
    first_thread = add_fake_thread(db.session, default_namespace.id)
    first_thread.subject = 'Some kind of test'

    msg1 = add_fake_message(db.session, default_namespace.id, first_thread)
    msg1.subject = 'Some kind of test'
    msg1.from_addr = [('Karim Hamidou', 'karim@nilas.com')]
    msg1.to_addr =   [('Karim Hamidou', 'karim@nilas.com')]

    msg2 = add_fake_message(db.session, default_namespace.id, thread=None)
    msg2.subject = 'Re: Some kind of test'
    msg2.from_addr = [('Karim Hamidou', 'karim@nilas.com')]
    msg2.to_addr =   [('Karim Hamidou', 'karim@nilas.com')]

    matched_thread = fetch_corresponding_thread(db.session, default_namespace.id, msg2)
    assert matched_thread is first_thread, "Should match on self-send"


if __name__ == '__main__':
    pytest.main([__file__])
