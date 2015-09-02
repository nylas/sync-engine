# -*- coding: utf-8 -*-
"""Sanity-check our construction of a Message object from raw synced data."""
import datetime
import pytest
from flanker import mime
from inbox.models import Message
from inbox.util.addr import parse_mimepart_address_header
from tests.util.base import (default_account, default_namespace, thread,
                             full_path, new_message_from_synced, mime_message)

__all__ = ['default_namespace', 'thread', 'default_account']


def create_from_synced(account, raw_message):
    received_date = datetime.datetime.utcnow()
    return Message.create_from_synced(account, 22, '[Gmail]/All Mail',
                                      received_date, raw_message)


@pytest.fixture
def raw_message_with_many_recipients():
    # Message carefully constructed s.t. the length of the serialized 'to'
    # field is 65536.
    raw_msg_path = full_path('../data/raw_message_with_many_recipients')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def mime_message_with_bad_date(mime_message):
    mime_message.headers['Date'] = 'unparseable'
    return mime_message


@pytest.fixture
def raw_message_with_long_content_id():
    # Message that has a long Content-ID
    raw_msg_path = full_path(
        '../data/raw_message_with_long_content_id')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_ical_invite():
    raw_msg_path = full_path('../data/raw_message_with_ical_invite')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_bad_attachment():
    # Message with a MIME part that has an invalid attachment.
    raw_msg_path = full_path(
        '../data/raw_message_with_bad_attachment')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_filename_attachment():
    # Message with a MIME part that has an invalid attachment.
    raw_msg_path = full_path(
        '../data/raw_message_with_filename_attachment')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_name_attachment():
    # Message with a MIME part that has an invalid attachment.
    raw_msg_path = full_path(
        '../data/raw_message_with_name_attachment')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_inline_name_attachment():
    # Message with a MIME part that has an invalid attachment.
    raw_msg_path = full_path(
        '../data/raw_message_with_inline_attachment')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_outlook_emoji():
    # Message with a MIME part that has an invalid attachment.
    raw_msg_path = full_path(
        '../data/raw_message_with_outlook_emoji')
    with open(raw_msg_path) as f:
        return f.read()


@pytest.fixture
def raw_message_with_outlook_emoji_inline():
    # Message with a MIME part that has an invalid attachment.
    raw_msg_path = full_path(
        '../data/raw_message_with_outlook_emoji_inline')
    with open(raw_msg_path) as f:
        return f.read()


def test_message_from_synced(db, new_message_from_synced, default_namespace):
    m = new_message_from_synced
    assert m.namespace_id == default_namespace.id
    assert m.to_addr == [['Alice', 'alice@example.com']]
    assert m.cc_addr == [['Bob', 'bob@example.com']]
    assert m.subject == 'Hello'
    assert m.body == '<html>Hello World!</html>'
    assert len(m.parts) == 0


def test_save_attachments(default_account):
    mime_msg = mime.create.multipart('mixed')
    mime_msg.append(
        mime.create.text('plain', 'This is a message with attachments'),
        mime.create.attachment('image/png', 'filler', 'attached_image.png',
                               'attachment'),
        mime.create.attachment('application/pdf', 'filler',
                               'attached_file.pdf', 'attachment')
    )
    msg = create_from_synced(default_account, mime_msg.to_string())
    assert len(msg.parts) == 2
    assert all(part.content_disposition == 'attachment' for part in msg.parts)
    assert {part.block.filename for part in msg.parts} == \
        {'attached_image.png', 'attached_file.pdf'}
    assert {part.block.content_type for part in msg.parts} == \
        {'image/png', 'application/pdf'}


def test_save_inline_attachments(default_account):
    mime_msg = mime.create.multipart('mixed')
    inline_attachment = mime.create.attachment('image/png', 'filler',
                                               'inline_image.png', 'inline')
    inline_attachment.headers['Content-Id'] = '<content_id@mailer.nylas.com>'
    mime_msg.append(inline_attachment)
    return mime_msg
    msg = create_from_synced(default_account, mime_message.to_string())
    assert len(msg.parts) == 1
    part = msg.parts[0]
    assert part.content_disposition == 'inline'
    assert part.content_id == '<content_id@mailer.nylas.com>'
    assert part.block.content_type == 'image/png'
    assert part.block.data == 'filler'


def test_concatenate_parts_for_body(default_account):
    # Test that when a message has multiple inline attachments / text parts, we
    # concatenate to form the text body (Apple Mail constructs such messages).
    # Example MIME structure:
    # multipart/mixed
    # |
    # +-text/html
    # |
    # +-image/jpeg
    # |
    # +-text/html
    # |
    # +-image/jpeg
    # |
    # +-text/html
    mime_msg = mime.create.multipart('mixed')
    mime_msg.append(
        mime.create.text('html', '<html>First part</html>'),
        mime.create.attachment('image/png', 'filler', disposition='inline'),
        mime.create.text('html', '<html>Second part</html>'),
        mime.create.attachment('image/png', 'more filler',
                               disposition='inline'),
        mime.create.text('html', '<html>3rd part</html>'),
    )
    m = create_from_synced(default_account, mime_msg.to_string())
    assert m.body == \
        '<html>First part</html><html>Second part</html><html>3rd part</html>'
    assert len(m.parts) == 2


def test_inline_parts_may_form_body_text(default_account):
    # Some clients (Slack) will set Content-Disposition: inline on text/plain
    # or text/html parts that are really just the body text. Check that we
    # don't save them as inline atrachments, but just use them to form the body
    # text.
    mime_msg = mime.create.multipart('mixed')
    mime_msg.append(
        mime.create.attachment('text/html', '<html>Hello World!</html>',
                               disposition='inline'),
        mime.create.attachment('text/plain', 'Hello World!',
                               disposition='inline')
    )
    m = create_from_synced(default_account, mime_msg.to_string())
    assert m.body == '<html>Hello World!</html>'
    assert len(m.parts) == 0


def test_convert_plaintext_body_to_html(default_account):
    mime_msg = mime.create.text('plain', 'Hello World!')
    m = create_from_synced(default_account, mime_msg.to_string())
    assert m.body == '<p>Hello World!</p>'


def test_save_parts_without_disposition_as_attachments(default_account):
    mime_msg = mime.create.multipart('mixed')
    mime_msg.append(
        mime.create.attachment('image/png', 'filler',
                               disposition=None)
    )
    m = create_from_synced(default_account, mime_msg.to_string())
    assert len(m.parts) == 1
    assert m.parts[0].content_disposition == 'attachment'
    assert m.parts[0].block.content_type == 'image/png'
    assert m.parts[0].block.data == 'filler'


def test_handle_long_filenames(default_account):
    mime_msg = mime.create.multipart('mixed')
    mime_msg.append(
        mime.create.attachment('image/png', 'filler',
                               filename=990 * 'A' + '.png',
                               disposition='attachment')
    )
    m = create_from_synced(default_account, mime_msg.to_string())
    assert len(m.parts) == 1
    saved_filename = m.parts[0].block.filename
    assert len(saved_filename) < 256
    # Check that we kept the extension
    assert saved_filename.endswith('.png')


def test_handle_long_subjects(default_account, mime_message):
    mime_message.headers['Subject'] = 4096 * 'A'
    m = create_from_synced(default_account, mime_message.to_string())
    assert len(m.subject) < 256


def test_dont_use_attached_html_to_form_body(default_account):
    mime_msg = mime.create.multipart('mixed')
    mime_msg.append(
        mime.create.text('plain', 'Please see attachment'),
        mime.create.attachment('text/html', '<html>This is attached</html>',
                               disposition='attachment',
                               filename='attachment.html')
    )
    m = create_from_synced(default_account, mime_msg.to_string())
    assert len(m.parts) == 1
    assert m.parts[0].content_disposition == 'attachment'
    assert m.parts[0].block.content_type == 'text/html'
    assert m.body == '<p>Please see attachment</p>'


def test_truncate_recipients(db, default_account, thread,
                             raw_message_with_many_recipients):
    m = create_from_synced(default_account, raw_message_with_many_recipients)
    m.thread = thread
    db.session.add(m)
    # Check that no database error is raised.
    db.session.commit()


def test_address_parsing():
    """Check that header parsing can handle a variety of tricky input."""
    # Extra quotes around display name
    mimepart = mime.from_string('From: ""Bob"" <bob@foocorp.com>')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [[' Bob ', 'bob@foocorp.com']]

    # Comments after addr-spec
    mimepart = mime.from_string(
        'From: "Bob" <bob@foocorp.com>(through Yahoo!  Store Order System)')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [['Bob', 'bob@foocorp.com']]

    mimepart = mime.from_string(
        'From: Indiegogo <noreply@indiegogo.com> (no reply)')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [['Indiegogo', 'noreply@indiegogo.com']]

    mimepart = mime.from_string(
        'From: Anon <support@github.com> (GitHub Staff)')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [['Anon', 'support@github.com']]

    # Display name in comment
    mimepart = mime.from_string('From: root@gunks (Cron Daemon)')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [['Cron Daemon', 'root@gunks']]

    # Missing closing angle bracket
    mimepart = mime.from_string('From: Bob <bob@foocorp.com')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [['Bob', 'bob@foocorp.com']]

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
    assert parsed == [['', 'bob@foocorp.com']]

    # RFC2047-encoded phrases with commas
    mimepart = mime.from_string(
        'From: =?utf-8?Q?Foo=2C=20Corp.?= <info@foocorp.com>')
    parsed = parse_mimepart_address_header(mimepart, 'From')
    assert parsed == [['Foo, Corp.', 'info@foocorp.com']]

    mimepart = mime.from_string(
        'To: =?utf-8?Q?Foo=2C=20Corp.?= <info@foocorp.com>, '
        '=?utf-8?Q?Support?= <support@foocorp.com>')
    parsed = parse_mimepart_address_header(mimepart, 'To')
    assert parsed == [['Foo, Corp.', 'info@foocorp.com'],
                      ['Support', 'support@foocorp.com']]

    # Multiple header lines
    mimepart = mime.from_string(
        'To: alice@foocorp.com\nSubject: Hello\nTo: bob@foocorp.com')
    parsed = parse_mimepart_address_header(mimepart, 'To')
    assert parsed == [['', 'alice@foocorp.com'], ['', 'bob@foocorp.com']]


def test_handle_bad_content_disposition(default_account, default_namespace,
                                        mime_message):
    # Message with a MIME part that has an invalid content-disposition.
    mime_message.append(
        mime.create.attachment('image/png', 'filler', 'attached_image.png',
                               disposition='alternative')
    )
    m = create_from_synced(default_account, mime_message.to_string())
    assert m.namespace_id == default_namespace.id
    assert m.to_addr == [['Alice', 'alice@example.com']]
    assert m.cc_addr == [['Bob', 'bob@example.com']]
    assert m.body == '<html>Hello World!</html>'
    assert len(m.parts) == 0


def test_store_full_body_on_parse_error(
        default_account, mime_message_with_bad_date):
    received_date = None
    m = Message.create_from_synced(default_account, 139219, '[Gmail]/All Mail',
                                   received_date,
                                   mime_message_with_bad_date.to_string())
    assert m.full_body


def test_long_content_id(db, default_account, thread,
                         raw_message_with_long_content_id):
    m = create_from_synced(default_account, raw_message_with_long_content_id)
    m.thread = thread
    db.session.add(m)
    # Check that no database error is raised.
    db.session.commit()


def test_parse_body_on_bad_attachment(
        default_account, raw_message_with_bad_attachment):
    received_date = None
    m = Message.create_from_synced(default_account, 139219, '[Gmail]/All Mail',
                                   received_date,
                                   raw_message_with_bad_attachment)
    assert m.decode_error
    assert 'dingy blue carpet' in m.body


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


def test_sanitize_subject(default_account, mime_message):
    # Parse a raw message with encoded null bytes in subject header;
    # check that we strip the null bytes.
    mime_message.headers['Subject'] = \
        '=?UTF-8?B?WW91ciBVUFMgUGFja2FnZSB3YXMgZGVsaXZlcmVkAAAA?='
    m = Message.create_from_synced(
        default_account, 22, '[Gmail]/All Mail', datetime.datetime.utcnow(),
        mime_message.to_string())
    assert m.subject == u'Your UPS Package was delivered'


def test_attachments_filename_parsing(default_account,
                                      raw_message_with_filename_attachment,
                                      raw_message_with_name_attachment):
    m = create_from_synced(default_account,
                           raw_message_with_filename_attachment)
    assert len(m.attachments) == 1
    assert m.attachments[0].block.filename == 'bewerbung_anschreiben_positivbeispiel.txt'

    m = create_from_synced(default_account,
                           raw_message_with_name_attachment)
    assert len(m.attachments) == 1
    assert m.attachments[0].block.filename == 'bewerbung_anschreiben_positivbeispiel.txt'


def test_inline_attachments_filename_parsing(default_account,
                                             raw_message_with_inline_name_attachment):
    m = create_from_synced(default_account,
                           raw_message_with_inline_name_attachment)
    assert len(m.attachments) == 1
    assert m.attachments[0].block.filename == u"Capture d'e\u0301cran 2015-08-13 20.58.24.png"


def test_attachments_emoji_filename_parsing(default_account,
                                            raw_message_with_outlook_emoji):
    m = create_from_synced(default_account,
                           raw_message_with_outlook_emoji)
    assert len(m.attachments) == 1
    assert m.attachments[0].block.filename == u'OutlookEmoji-\U0001f60a.png'
    assert m.attachments[0].block.content_type == 'image/png'
    assert m.attachments[0].content_id == '<3f0ea351-779e-48b3-bfa9-7c2a9e373aeb>'
    assert m.attachments[0].content_disposition == 'attachment'


def test_attachments_emoji_filename_parsing(default_account,
                                            raw_message_with_outlook_emoji_inline):
    m = create_from_synced(default_account,
                           raw_message_with_outlook_emoji_inline)
    assert len(m.attachments) == 1
    assert m.attachments[0].block.filename == u'OutlookEmoji-\U0001f60a.png'
    assert m.attachments[0].block.content_type == 'image/png'
    assert m.attachments[0].content_id == '<3f0ea351-779e-48b3-bfa9-7c2a9e373aeb>'
    assert m.attachments[0].content_disposition == 'inline'
