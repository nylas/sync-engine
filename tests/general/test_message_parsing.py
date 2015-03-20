# -*- coding: utf-8 -*-
"""Sanity-check our construction of a Message object from raw synced data."""
import datetime
import os
import pytest
from flanker import mime
from inbox.models import Message
from inbox.models.message import _get_errfilename
from inbox.util.addr import parse_mimepart_address_header
from tests.util.base import (default_account, default_namespace,
                             thread, add_fake_calendar)

__all__ = ['default_namespace', 'thread']


def full_path(relpath):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relpath)


@pytest.fixture
def raw_message():
    raw_msg_path = full_path('../data/raw_message')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_many_recipients():
    # Message carefully constructed s.t. the length of the serialized 'to'
    # field is 65536.
    raw_msg_path = full_path('../data/raw_message_with_many_recipients')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_bad_content_disposition():
    # Message with a MIME part that has an invalid content-disposition.
    raw_msg_path = full_path(
        '../data/raw_message_with_bad_content_disposition')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_bad_date():
    # Message with a MIME part that has an invalid content-disposition.
    raw_msg_path = full_path(
        '../data/raw_message_with_bad_date')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_ical_invite():
    raw_msg_path = full_path('../data/raw_message_with_ical_invite')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def new_message_from_synced(db):
    received_date = datetime.datetime(2014, 9, 22, 17, 25, 46)
    new_msg = Message.create_from_synced(default_account(db),
                                         139219,
                                         '[Gmail]/All Mail',
                                         received_date,
                                         raw_message())
    assert new_msg.received_date == received_date
    return new_msg


def test_message_from_synced(db, default_account, default_namespace,
                             raw_message):
    m = new_message_from_synced(db)
    assert m.namespace_id == default_namespace.id
    assert sorted(m.to_addr) == [(u'', u'csail-all.lists@mit.edu'),
                                 (u'', u'csail-announce@csail.mit.edu'),
                                 (u'', u'csail-related@csail.mit.edu')]
    assert len(m.parts) == 4
    assert 'Attached Message Part' in [part.block.filename for part in m.parts]
    assert all(part.block.namespace_id == m.namespace_id for part in m.parts)


def test_truncate_recipients(db, default_account, default_namespace, thread,
                             raw_message_with_many_recipients):
    received_date = datetime.datetime(2014, 9, 22, 17, 25, 46)
    m = Message.create_from_synced(default_account, 139219, '[Gmail]/All Mail',
                                   received_date,
                                   raw_message_with_many_recipients)
    m.thread = thread
    db.session.add(m)
    # Check that no database error is raised.
    db.session.commit()


def test_decode_error_file():
    """Test that we can save decode errors from non-Unicode folders without
    getting UnicodeEncodeErrors"""
    fname = _get_errfilename(1, u'迷惑メール', 22)
    os.rmdir(os.path.dirname(fname))


def test_address_parsing_edge_cases():
    """Check that header parsing can handle a variety of tricky input."""
    # Extra quotes around display name
    mimepart = mime.from_string('From: ""Bob"" <bob@foocorp.com>')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [(' Bob ', 'bob@foocorp.com')]

    # Comments after addr-spec
    mimepart = mime.from_string(
        'From: "Bob" <bob@foocorp.com>(through Yahoo!  Store Order System)')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [('Bob', 'bob@foocorp.com')]

    mimepart = mime.from_string(
        'From: Indiegogo <noreply@indiegogo.com> (no reply)')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [('Indiegogo', 'noreply@indiegogo.com')]

    mimepart = mime.from_string(
        'From: Anon <support@github.com> (GitHub Staff)')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [('Anon', 'support@github.com')]

    # Display name in comment
    mimepart = mime.from_string('From: root@gunks (Cron Daemon)')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [('Cron Daemon', 'root@gunks')]

    # Missing closing angle bracket
    mimepart = mime.from_string('From: Bob <bob@foocorp.com')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [('Bob', 'bob@foocorp.com')]

    # Blank (spammers)
    mimepart = mime.from_string('From:  ()')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == []

    # Missing header
    mimepart = mime.from_string('')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == []

    # Duplicate header
    mimepart = mime.from_string('From: bob@foocorp.com\r\n'
                                'From: bob@foocorp.com')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [('', 'bob@foocorp.com')]


def test_handle_bad_content_disposition(
        default_account, default_namespace,
        raw_message_with_bad_content_disposition):
    received_date = datetime.datetime(2014, 9, 22, 17, 25, 46)
    m = Message.create_from_synced(default_account, 139219, '[Gmail]/All Mail',
                                   received_date,
                                   raw_message_with_bad_content_disposition)
    assert m.namespace_id == default_namespace.id
    assert sorted(m.to_addr) == [(u'', u'csail-all.lists@mit.edu'),
                                 (u'', u'csail-announce@csail.mit.edu'),
                                 (u'', u'csail-related@csail.mit.edu')]
    assert len(m.parts) == 3
    assert m.received_date == received_date
    assert all(part.block.namespace_id == m.namespace_id for part in m.parts)


def test_store_full_body_on_parse_error(
        default_account, default_namespace,
        raw_message_with_bad_date):
    received_date = None
    m = Message.create_from_synced(default_account, 139219, '[Gmail]/All Mail',
                                   received_date,
                                   raw_message_with_bad_date)
    assert m.full_body


def test_calculate_snippet():
    m = Message()
    # Check that we strip contents of title, script, style tags
    body = '<title>EMAIL</title><script>function() {}</script>' \
           '<style>h1 {color:red;}</style>Hello, world'
    assert m.calculate_html_snippet(body) == 'Hello, world'

    # Check that we replace various incarnations of <br> by spaces
    body = 'Hello,<br>world'
    assert m.calculate_html_snippet(body) == 'Hello, world'

    body = 'Hello,<br class=\"\">world'
    assert m.calculate_html_snippet(body) == 'Hello, world'

    body = 'Hello,<br />world'
    assert m.calculate_html_snippet(body) == 'Hello, world'

    body = 'Hello,<br><br> world'
    assert m.calculate_html_snippet(body) == 'Hello, world'

    # Check that snippets are properly truncated to 191 characters.
    body = '''Etenim quid est, <strong>Catilina</strong>, quod iam amplius
              exspectes, si neque nox tenebris obscurare coetus nefarios nec
              privata domus parietibus continere voces coniurationis tuae
              potest, si illustrantur, si erumpunt omnia?'''
    expected_snippet = 'Etenim quid est, Catilina, quod iam amplius ' \
                       'exspectes, si neque nox tenebris obscurare coetus ' \
                       'nefarios nec privata domus parietibus continere ' \
                       'voces coniurationis tuae potest, si illustrantur,'
    assert len(expected_snippet) == 191
    assert m.calculate_html_snippet(body) == expected_snippet


@pytest.mark.only
def test_integrated_ical_parsing(
        db, default_account, default_namespace,
        raw_message_with_ical_invite):
    cal = default_account.emailed_events_calendar
    received_date = datetime.datetime(2014, 9, 22, 17, 25, 46)
    m = Message.create_from_synced(default_account, 139219, '[Gmail]/All Mail',
                                   received_date,
                                   raw_message_with_ical_invite)
    assert len(cal.events) == 1
    assert cal.events[0].title == 'Nilas test drive'
