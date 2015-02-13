# -*- coding: utf-8 -*-
import smtplib
import json
import pytest
from flanker import mime
from inbox.basicauth import OAuthError
from inbox.models import Message
from tests.util.base import api_client, default_account


class MockTokenManager(object):
    def __init__(self, allow_auth=True):
        self.allow_auth = allow_auth

    def get_token(self, account, force_refresh=True):
        if self.allow_auth:
            # return a fake token.
            return 'foo'
        raise OAuthError()


@pytest.fixture
def patch_token_manager(monkeypatch):
    monkeypatch.setattr('inbox.sendmail.smtp.postel.token_manager',
                        MockTokenManager())


@pytest.fixture
def disallow_auth(monkeypatch):
    monkeypatch.setattr('inbox.sendmail.smtp.postel.token_manager',
                        MockTokenManager(allow_auth=False))


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


@pytest.fixture
def example_draft(db):
    from inbox.models import Account
    account = db.session.query(Account).get(1)
    return {
        'subject': 'Draft test',
        'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>',
        'to': [{'name': 'The red-haired mermaid',
                'email': account.email_address}]
    }


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
    threads_with_drafts = api_client.get_data('/threads?tag=drafts')
    assert not drafts
    assert not threads_with_drafts

    sent_threads = api_client.get_data('/threads?tag=sent')
    assert len(sent_threads) == 1

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
    sent_threads = api_client.get_data('/threads?tag=sent')
    assert len(sent_threads) == 1


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


def test_reply_headers_set(patch_smtp, api_client, example_draft):
    thread_id = api_client.get_data('/threads')[0]['id']

    api_client.post_data('/send', {'to': [{'email': 'bob@foocorp.com'}],
                                   'thread_id': thread_id})
    _, msg = patch_smtp[-1]
    parsed = mime.from_string(msg)
    assert 'In-Reply-To' in parsed.headers
    assert 'References' in parsed.headers


def test_draft_not_persisted_if_sending_fails(recipients_refused, api_client,
                                              db):
    api_client.post_data('/send', {'to': [{'email': 'bob@foocorp.com'}],
                                   'subject': 'some unique subject'})
    assert db.session.query(Message).filter_by(
        subject='some unique subject').first() is None
