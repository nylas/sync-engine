# -*- coding: utf-8 -*-
"""Sanity-check our construction of a Message object from raw synced data."""
import datetime
import os
import pytest
from inbox.models import Message, Account
from inbox.models.message import _get_errfilename

ACCOUNT_ID = 1
NAMESPACE_ID = 1


@pytest.fixture
def raw_message():
    raw_msg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '../data/raw_message')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_many_recipients():
    # Message carefully constructed s.t. the length of the serialized 'to'
    # field is 65536.
    raw_msg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '../data/raw_message_with_many_recipients')
    with open(raw_msg_path) as f:
        return f.read()


def test_message_from_synced(db, raw_message):
    account = db.session.query(Account).get(ACCOUNT_ID)
    assert account.namespace.id == NAMESPACE_ID
    received_date = datetime.datetime(2014, 9, 22, 17, 25, 46),
    m = Message.create_from_synced(account, 139219, '[Gmail]/All Mail',
                                   received_date, raw_message)
    assert m.namespace_id == NAMESPACE_ID
    assert sorted(m.to_addr) == [(u'', u'csail-all.lists@mit.edu'),
                                 (u'', u'csail-announce@csail.mit.edu'),
                                 (u'', u'csail-related@csail.mit.edu')]
    assert len(m.parts) == 8
    assert 'Attached Message Part' in [part.block.filename for part in m.parts]
    assert m.received_date == received_date
    assert all(part.block.namespace_id == m.namespace_id for part in m.parts)


def test_truncate_recipients(db, raw_message_with_many_recipients):
    account = db.session.query(Account).get(ACCOUNT_ID)
    assert account.namespace.id == NAMESPACE_ID
    received_date = datetime.datetime(2014, 9, 22, 17, 25, 46),
    m = Message.create_from_synced(account, 139219, '[Gmail]/All Mail',
                                   received_date,
                                   raw_message_with_many_recipients)
    m.thread_id = 1
    db.session.add(m)
    # Check that no database error is raised.
    db.session.commit()


def test_decode_error_file():
    """Test that we can save decode errors from non-Unicode folders without
    getting UnicodeEncodeErrors"""
    fname = _get_errfilename(1, u'迷惑メール', 22)
    os.rmdir(os.path.dirname(fname))
