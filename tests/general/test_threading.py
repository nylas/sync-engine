# -*- coding: utf-8 -*-
import pytest
from datetime import datetime
from inbox.util.threading import cleanup_subject, thread_messages
from collections import namedtuple


def test_message_cleanup():
    assert cleanup_subject("Re: Birthday") == "Birthday"
    assert cleanup_subject("Re:Birthday") == "Birthday"
    assert cleanup_subject("Re:FWD:   Birthday") == "Birthday"
    assert (cleanup_subject("Re: RE: Alors, comment ça s'est passé ?")
                == "Alors, comment ça s'est passé ?")
    assert cleanup_subject("Re: FWD:FWD: Re:La chaise") == "La chaise"


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



# hack but my test won't run in the test runner. All the
# tests hang.
if __name__ == '__main__':
    pytest.main([__file__])
