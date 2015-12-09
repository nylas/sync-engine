# -*- coding: utf-8 -*-
import smtplib
import json
import time
import pytest
from flanker import mime
from inbox.basicauth import OAuthError
from inbox.models import Message, Event
from tests.util.base import thread, message, imported_event
from tests.api.base import api_client


__all__ = ['thread', 'message', 'api_client', 'imported_event']


class MockTokenManager(object):

    def __init__(self, allow_auth=True):
        self.allow_auth = allow_auth

    def get_token(self, account, force_refresh=True):
        if self.allow_auth:
            # return a fake token.
            return 'foo'
        raise OAuthError()


class MockGoogleTokenManager(object):

    def __init__(self, allow_auth=True):
        self.allow_auth = allow_auth

    def get_token_for_email(self, account, force_refresh=False):
        if self.allow_auth:
            return 'foo'
        raise OAuthError()


@pytest.fixture
def patch_token_manager(monkeypatch):
    monkeypatch.setattr('inbox.sendmail.smtp.postel.default_token_manager',
                        MockTokenManager())
    monkeypatch.setattr('inbox.sendmail.smtp.postel.g_token_manager',
                        MockGoogleTokenManager())


@pytest.fixture
def disallow_auth(monkeypatch):
    monkeypatch.setattr('inbox.sendmail.smtp.postel.default_token_manager',
                        MockTokenManager(allow_auth=False))
    monkeypatch.setattr('inbox.sendmail.smtp.postel.g_token_manager',
                        MockGoogleTokenManager(allow_auth=False))


@pytest.fixture
def patch_smtp(patch_token_manager, monkeypatch):
    submitted_messages = []

    class MockSMTPConnection(object):

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, value, traceback):
            pass

        def sendmail(self, recipients, msg):
            submitted_messages.append((recipients, msg))

    monkeypatch.setattr('inbox.sendmail.smtp.postel.SMTPConnection',
                        MockSMTPConnection)
    return submitted_messages


def erring_smtp_connection(exc_type, *args):
    class ErringSMTPConnection(object):

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, value, traceback):
            pass

        def sendmail(self, recipients, msg):
            raise exc_type(*args)

    return ErringSMTPConnection


@pytest.fixture
def quota_exceeded(patch_token_manager, monkeypatch):
    monkeypatch.setattr('inbox.sendmail.smtp.postel.SMTPConnection',
                        erring_smtp_connection(
                            smtplib.SMTPDataError, 550,
                            '5.4.5 Daily sending quota exceeded'))


@pytest.fixture
def connection_closed(patch_token_manager, monkeypatch):
    monkeypatch.setattr('inbox.sendmail.smtp.postel.SMTPConnection',
                        erring_smtp_connection(smtplib.SMTPServerDisconnected))


@pytest.fixture
def recipients_refused(patch_token_manager, monkeypatch):
    monkeypatch.setattr('inbox.sendmail.smtp.postel.SMTPConnection',
                        erring_smtp_connection(smtplib.SMTPRecipientsRefused,
                                               {'foo@foocorp.com':
                                                (550, 'User unknown')}))


# Different providers use slightly different errors, so parametrize this test
# fixture to imitate them.
@pytest.fixture(params=[
    "5.2.3 Your message exceeded Google's message size limits"
    "5.3.4 Message size exceeds fixed maximum message size"])
def message_too_large(patch_token_manager, monkeypatch, request):
    monkeypatch.setattr(
        'inbox.sendmail.smtp.postel.SMTPConnection',
        erring_smtp_connection(
            smtplib.SMTPSenderRefused, 552,
            request.param, None))


@pytest.fixture
def insecure_content(patch_token_manager, monkeypatch):
    monkeypatch.setattr(
        'inbox.sendmail.smtp.postel.SMTPConnection',
        erring_smtp_connection(
            smtplib.SMTPDataError, 552,
            '5.7.0 This message was blocked because its content presents a '
            'potential\\n5.7.0 security issue.'))


@pytest.fixture
def example_draft(db, default_account):
    return {
        'subject': 'Draft test',
        'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>',
        'to': [{'name': 'The red-haired mermaid',
                'email': default_account.email_address}]
    }


@pytest.fixture
def example_rsvp(imported_event):
    return {
        'event_id': imported_event.public_id,
        'comment': 'I will come.',
        'status': 'yes',
    }


@pytest.fixture
def example_draft_bad_subject(db, default_account):
    return {
        'subject': ['draft', 'test'],
        'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>',
        'to': [{'name': 'The red-haired mermaid',
                'email': default_account.email_address}]
    }


@pytest.fixture
def example_draft_bad_body(db, default_account):
    return {
        'subject': 'Draft test',
        'body': {'foo': 'bar'},
        'to': [{'name': 'The red-haired mermaid',
                'email': default_account.email_address}]
    }


@pytest.fixture
def example_event(db, api_client):
    from inbox.models.calendar import Calendar
    cal = db.session.query(Calendar).get(1)

    event = {
        'title': 'Invite test',
        'when': {
            "end_time": 1436210662,
            "start_time": 1436207062
        },
        'participants': [
            {'email': 'helena@nylas.com'}
        ],
        'calendar_id': cal.public_id,
    }

    r = api_client.post_data('/events', event)
    event_public_id = json.loads(r.data)['id']
    return event_public_id


def test_send_existing_draft(patch_smtp, api_client, example_draft):
    r = api_client.post_data('/drafts', example_draft)
    draft_public_id = json.loads(r.data)['id']
    version = json.loads(r.data)['version']

    r = api_client.post_data('/send',
                             {'draft_id': draft_public_id,
                              'version': version})
    assert r.status_code == 200

    # Test that the sent draft can't be sent again.
    r = api_client.post_data('/send',
                             {'draft_id': draft_public_id,
                              'version': version})
    assert r.status_code == 400

    drafts = api_client.get_data('/drafts')
    assert not drafts

    message = api_client.get_data('/messages/{}'.format(draft_public_id))
    assert message['object'] == 'message'


def test_send_rejected_without_version(api_client, example_draft):
    r = api_client.post_data('/drafts', example_draft)
    draft_public_id = json.loads(r.data)['id']
    r = api_client.post_data('/send', {'draft_id': draft_public_id})
    assert r.status_code == 400


def test_send_rejected_with_wrong_version(api_client, example_draft):
    r = api_client.post_data('/drafts', example_draft)
    draft_public_id = json.loads(r.data)['id']
    r = api_client.post_data('/send', {'draft_id': draft_public_id,
                                       'version': 222})
    assert r.status_code == 409


def test_send_rejected_without_recipients(api_client):
    r = api_client.post_data('/drafts', {'subject': 'Hello there'})
    draft_public_id = json.loads(r.data)['id']
    version = json.loads(r.data)['version']

    r = api_client.post_data('/send',
                             {'draft_id': draft_public_id,
                              'version': version})
    assert r.status_code == 400


def test_send_new_draft(patch_smtp, api_client, default_account,
                        example_draft):
    r = api_client.post_data('/send', example_draft)
    assert r.status_code == 200


def test_malformed_body_rejected(api_client, example_draft_bad_body):
    r = api_client.post_data('/send', example_draft_bad_body)

    assert r.status_code == 400

    decoded = json.loads(r.get_data())
    assert decoded['type'] == 'invalid_request_error'
    assert decoded['message'] == '"body" should be a string'


def test_malformed_subject_rejected(api_client, example_draft_bad_subject):
    r = api_client.post_data('/send', example_draft_bad_subject)
    assert r.status_code == 400

    decoded = json.loads(r.get_data())
    assert decoded['type'] == 'invalid_request_error'
    assert decoded['message'] == '"subject" should be a string'


def test_malformed_request_rejected(api_client):
    r = api_client.post_data('/send', {})
    assert r.status_code == 400


def test_recipient_validation(patch_smtp, api_client):
    r = api_client.post_data('/drafts', {'to': [{'email': 'foo@example.com'}]})
    assert r.status_code == 200
    r = api_client.post_data('/drafts', {'to': {'email': 'foo@example.com'}})
    assert r.status_code == 400
    r = api_client.post_data('/drafts', {'to': 'foo@example.com'})
    assert r.status_code == 400
    r = api_client.post_data('/drafts', {'to': [{'name': 'foo'}]})
    assert r.status_code == 400
    r = api_client.post_data('/send', {'to': [{'email': 'foo'}]})
    assert r.status_code == 400
    r = api_client.post_data('/send', {'to': [{'email': 'föö'}]})
    assert r.status_code == 400
    r = api_client.post_data('/drafts', {'to': [{'email': ['foo']}]})
    assert r.status_code == 400
    r = api_client.post_data('/drafts', {'to': [{'name': ['Mr. Foo'],
                                                 'email': 'foo@example.com'}]})
    assert r.status_code == 400
    r = api_client.post_data('/drafts',
                             {'to': [{'name': 'Good Recipient',
                                      'email': 'goodrecipient@example.com'},
                                     'badrecipient@example.com']})
    assert r.status_code == 400

    # Test that sending a draft with invalid recipients fails.
    for field in ('to', 'cc', 'bcc'):
        r = api_client.post_data('/drafts', {field: [{'email': 'foo'}]})
        draft_id = json.loads(r.data)['id']
        draft_version = json.loads(r.data)['version']
        r = api_client.post_data('/send', {'draft_id': draft_id,
                                           'draft_version': draft_version})
        assert r.status_code == 400


def test_handle_invalid_credentials(disallow_auth, api_client, example_draft):
    r = api_client.post_data('/send', example_draft)
    assert r.status_code == 403
    assert json.loads(r.data)['message'] == 'Could not authenticate with ' \
                                            'the SMTP server.'


def test_handle_quota_exceeded(quota_exceeded, api_client, example_draft):
    r = api_client.post_data('/send', example_draft)
    assert r.status_code == 429
    assert json.loads(r.data)['message'] == 'Daily sending quota exceeded'


def test_handle_server_disconnected(connection_closed, api_client,
                                    example_draft):
    r = api_client.post_data('/send', example_draft)
    assert r.status_code == 503
    assert json.loads(r.data)['message'] == 'The server unexpectedly closed ' \
                                            'the connection'


def test_handle_recipients_rejected(recipients_refused, api_client,
                                    example_draft):
    r = api_client.post_data('/send', example_draft)
    assert r.status_code == 402
    assert json.loads(r.data)['message'] == 'Sending to all recipients failed'


def test_handle_message_too_large(message_too_large, api_client,
                                  example_draft):
    r = api_client.post_data('/send', example_draft)
    assert r.status_code == 402
    assert json.loads(r.data)['message'] == 'Message too large'


def test_message_rejected_for_security(insecure_content, api_client,
                                       example_draft):
    r = api_client.post_data('/send', example_draft)
    assert r.status_code == 402
    assert json.loads(r.data)['message'] == \
        'Message content rejected for security reasons'


def test_bcc_in_recipients_but_stripped_from_headers(patch_smtp, api_client):
    r = api_client.post_data(
        '/send',
        {
            'to': [{'email': 'bob@foocorp.com'}],
            'cc': [{'email': 'jane@foocorp.com'}],
            'bcc': [{'email': 'spies@nsa.gov'}],
            'subject': 'Banalities'
        })
    assert r.status_code == 200
    recipients, msg = patch_smtp[0]
    assert set(recipients) == {'bob@foocorp.com', 'jane@foocorp.com',
                               'spies@nsa.gov'}
    parsed = mime.from_string(msg)
    assert 'Bcc' not in parsed.headers
    assert parsed.headers.get('To') == 'bob@foocorp.com'
    assert parsed.headers.get('Cc') == 'jane@foocorp.com'


def test_reply_headers_set(db, patch_smtp, api_client, example_draft, thread,
                           message):
    message.message_id_header = '<exampleheader@example.com>'
    db.session.commit()
    thread_id = api_client.get_data('/threads')[0]['id']

    api_client.post_data('/send', {'to': [{'email': 'bob@foocorp.com'}],
                                   'thread_id': thread_id})
    _, msg = patch_smtp[-1]
    parsed = mime.from_string(msg)
    assert 'In-Reply-To' in parsed.headers
    assert 'References' in parsed.headers


def test_body_construction(patch_smtp, api_client):
    api_client.post_data('/send',
                         {'to': [{'email': 'bob@foocorp.com'}],
                          'subject': 'Banalities',
                          'body': '<html>Hello there</html>'})
    _, msg = patch_smtp[-1]
    parsed = mime.from_string(msg)
    assert len(parsed.parts) == 2
    plain_part_found = False
    html_part_found = False
    for part in parsed.parts:
        if part.content_type.value == 'text/plain':
            plain_part_found = True
            assert part.body.strip() == 'Hello there'
        elif part.content_type.value == 'text/html':
            html_part_found = True
            assert part.body.strip() == '<html>Hello there</html>'
    assert plain_part_found and html_part_found


def test_quoted_printable_encoding_avoided_for_compatibility(
        patch_smtp, api_client):
    # Test that messages with long lines don't get quoted-printable encoded,
    # for maximum server compatibility.
    api_client.post_data(
        '/send',
        {'to': [{'email': 'bob@foocorp.com'}],
         'subject': 'In Catilinam',
         'body': 'Etenim quid est, Catilina, quod iam amplius exspectes, si '
         'neque nox tenebris obscurare coeptus nefarios neque privata domus '
         'parietibus continere voces conjurationis tuae potest? Si '
         'illustrantur, si erumpunt omnia? Muta iam istam mentem, mihi crede! '
         'obliviscere caedis atque incendiorum. Teneris undique: luce sunt '
         'clariora nobis tua consilia omnia; quae iam mecum licet recognoscas.'
         ' Meministine me ante diem duodecimum Kalendas Novembres dicere in '
         'senatu, fore in armis certo die, qui dies futurus esset ante diem '
         'sextum Kalendas Novembres, C. Manlium, audaciae satellitem atque '
         'administrum tuae? Num me fefellit, Catilina, non modo res tanta, tam'
         ' atrox, tamque incredibilis, verum id quod multo magis admirandum, '
         'dies? '})
    _, msg = patch_smtp[-1]
    parsed = mime.from_string(msg)
    assert len(parsed.parts) == 2
    for part in parsed.parts:
        if part.content_type.value == 'text/html':
            assert part.content_encoding[0] == 'base64'
        elif part.content_type.value == 'text/plain':
            assert part.content_encoding[0] in ('7bit', 'base64')


def test_draft_not_persisted_if_sending_fails(recipients_refused, api_client,
                                              db):
    api_client.post_data('/send', {'to': [{'email': 'bob@foocorp.com'}],
                                   'subject': 'some unique subject'})
    assert db.session.query(Message).filter_by(
        subject='some unique subject').first() is None


def test_setting_reply_to_headers(patch_smtp, api_client):
    api_client.post_data('/send',
                         {'to': [{'email': 'bob@foocorp.com'}],
                          'reply_to': [{'name': 'admin',
                                        'email': 'prez@whitehouse.gov'}],
                          'subject': 'Banalities',
                          'body': '<html>Hello there</html>'})
    _, msg = patch_smtp[-1]
    parsed = mime.from_string(msg)
    assert 'Reply-To' in parsed.headers
    assert parsed.headers['Reply-To'] == 'admin <prez@whitehouse.gov>'


def test_sending_from_email_alias(patch_smtp, api_client):
    api_client.post_data('/send',
                         {'to': [{'email': 'bob@foocorp.com'}],
                          'from': [{'name': 'admin',
                                    'email': 'prez@whitehouse.gov'}],
                          'subject': 'Banalities',
                          'body': '<html>Hello there</html>'})
    _, msg = patch_smtp[-1]
    parsed = mime.from_string(msg)
    assert 'From' in parsed.headers
    assert parsed.headers['From'] == 'admin <prez@whitehouse.gov>'


def test_sending_raw_mime(patch_smtp, api_client):
    api_client.post_raw('/send', ('From: bob@foocorp.com\r\n'
                                    'To: golang-nuts '
                                    '<golang-nuts@googlegroups.com>\r\n'
                                    'Cc: prez@whitehouse.gov\r\n'
                                    'Bcc: Some Guy <masterchief@halo.com>\r\n'
                                    'Subject: '
                                    '[go-nuts] Runtime Panic On Method Call'
                                    '\r\n'
                                    'Mime-Version: 1.0\r\n'
                                    'In-Reply-To: '
                                    '<78pgxboai332pi9p2smo4db73-0'
                                    '@mailer.nylas.com>\r\n'
                                    'References: '
                                    '<78pgxboai332pi9p2smo4db73-0'
                                    '@mailer.nylas.com>\r\n'
                                    'Content-Type: text/plain; charset=UTF-8'
                                    '\r\n'
                                    'Content-Transfer-Encoding: 7bit\r\n'
                                    'X-My-Custom-Header: Random\r\n\r\n'
                                    'Yo.'), headers={'Content-Type':
                                                        'message/rfc822'})

    _, msg = patch_smtp[-1]
    parsed = mime.from_string(msg)
    assert parsed.body == 'Yo.'
    assert parsed.headers['From'] == 'bob@foocorp.com'
    assert parsed.headers['Subject'] == \
                            '[go-nuts] Runtime Panic On Method Call'
    assert parsed.headers['Cc'] == 'prez@whitehouse.gov'
    assert parsed.headers['To'] == \
                            'golang-nuts <golang-nuts@googlegroups.com>'
    assert parsed.headers['In-Reply-To'] == \
                            '<78pgxboai332pi9p2smo4db73-0@mailer.nylas.com>'
    assert parsed.headers['References'] == \
                            '<78pgxboai332pi9p2smo4db73-0@mailer.nylas.com>'
    assert parsed.headers['X-My-Custom-Header'] == 'Random'
    assert 'Bcc' not in parsed.headers
    assert 'X-INBOX-ID' in parsed.headers
    assert 'Message-Id' in parsed.headers
    assert 'User-Agent' in parsed.headers


def test_sending_bad_raw_mime(patch_smtp, api_client):
    res = api_client.post_raw('/send', ('From: bob@foocorp.com\r\n'
                                        'To: \r\n'
                                        'Subject: '
                                        '[go-nuts] Runtime Panic On Method'
                                        'Call \r\n'
                                        'Mime-Version: 1.0\r\n'
                                        'Content-Type: '
                                        'text/plain; charset=UTF-8\r\n'
                                        'Content-Transfer-Encoding: 7bit\r\n'
                                        'X-My-Custom-Header: Random'
                                        '\r\n\r\n'
                                        'Yo.'), headers={'Content-Type':
                                                            'message/rfc822'})

    assert res.status_code == 400


def test_sending_from_email_multiple_aliases(patch_smtp, patch_token_manager,
                                             api_client):
    res = api_client.post_data('/send',
                               {'to': [{'email': 'bob@foocorp.com'}],
                                'from': [{'name': 'admin',
                                          'email': 'prez@whitehouse.gov'},
                                         {'name': 'the rock',
                                          'email': 'd.johnson@gmail.com'}],
                                'subject': 'Banalities',
                                'body': '<html>Hello there</html>'})
    assert res.status_code == 400

    res = api_client.post_data('/send',
                               {'to': [{'email': 'bob@foocorp.com'}],
                                'reply_to': [{'name': 'admin',
                                              'email': 'prez@whitehouse.gov'},
                                             {'name': 'the rock',
                                              'email': 'd.johnson@gmail.com'}],
                                'subject': 'Banalities',
                                'body': '<html>Hello there</html>'})
    assert res.status_code == 400


def test_rsvp_invalid_credentials(disallow_auth, api_client, example_rsvp):
    r = api_client.post_data('/send-rsvp', example_rsvp)
    assert r.status_code == 403
    assert json.loads(r.data)['message'] == 'Could not authenticate with ' \
                                            'the SMTP server.'


def test_rsvp_quota_exceeded(quota_exceeded, api_client, example_rsvp):
    r = api_client.post_data('/send-rsvp', example_rsvp)
    assert r.status_code == 429
    assert json.loads(r.data)['message'] == 'Daily sending quota exceeded'


def test_rsvp_server_disconnected(connection_closed, api_client, example_rsvp):
    r = api_client.post_data('/send-rsvp', example_rsvp)
    assert r.status_code == 503
    assert json.loads(r.data)['message'] == 'The server unexpectedly closed ' \
                                            'the connection'


def test_rsvp_recipients_rejected(recipients_refused, api_client,
                                  example_rsvp):
    r = api_client.post_data('/send-rsvp', example_rsvp)
    assert r.status_code == 402
    assert json.loads(r.data)['message'] == 'Sending to all recipients failed'


def test_rsvp_message_too_large(message_too_large, api_client, example_rsvp):
    r = api_client.post_data('/send-rsvp', example_rsvp)
    assert r.status_code == 402
    assert json.loads(r.data)['message'] == 'Message too large'


def test_rsvp_message_rejected_for_security(insecure_content, api_client,
                                            example_rsvp):
    r = api_client.post_data('/send-rsvp', example_rsvp)
    assert r.status_code == 402
    assert json.loads(r.data)['message'] == \
        'Message content rejected for security reasons'


def test_rsvp_updates_status(patch_smtp, api_client, example_rsvp,
                             imported_event):
    assert len(imported_event.participants) == 1
    assert imported_event.participants[0]['email'] == 'inboxapptest@gmail.com'
    assert imported_event.participants[0]['status'] == 'noreply'

    r = api_client.post_data('/send-rsvp', example_rsvp)
    assert r.status_code == 200
    dct = json.loads(r.data)

    # check that the event's status got updated
    assert len(dct['participants']) == 1
    assert dct['participants'][0]['email'] == 'inboxapptest@gmail.com'
    assert dct['participants'][0]['status'] == 'yes'
    assert dct['participants'][0]['comment'] == 'I will come.'


def test_rsvp_idempotent(db, patch_smtp, api_client, example_rsvp,
                         imported_event):
    imported_event.participants[0]['status'] = example_rsvp['status']
    imported_event.participants[0]['comment'] = example_rsvp['comment']
    db.session.commit()
    old_update_date = imported_event.updated_at
    db.session.expunge(imported_event)

    r = api_client.post_data('/send-rsvp', example_rsvp)
    assert r.status_code == 200
    dct = json.loads(r.data)

    # check that the event's status is the same.
    assert len(dct['participants']) == 1
    assert dct['participants'][0]['email'] == 'inboxapptest@gmail.com'
    assert dct['participants'][0]['status'] == 'yes'
    assert dct['participants'][0]['comment'] == 'I will come.'

    # Check that the event hasn't been updated.
    refreshed_event = db.session.query(Event).get(imported_event.id)
    assert refreshed_event.updated_at == old_update_date


def test_sent_messages_shown_in_delta(patch_smtp, api_client, example_draft):
    ts = int(time.time())
    r = api_client.post_data('/delta/generate_cursor', {'start': ts})
    cursor = json.loads(r.data)['cursor']
    r = api_client.post_data('/send', example_draft)
    message_id = json.loads(r.data)['id']
    deltas = api_client.get_data('/delta?cursor={}'.format(cursor))['deltas']
    message_delta = next((d for d in deltas if d['id'] == message_id), None)
    assert message_delta is not None
    assert message_delta['object'] == 'message'
    assert message_delta['event'] == 'create'
