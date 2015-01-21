import pytest
from imapclient import IMAPClient
from mock import Mock

from inbox.models.session import session_scope
from inbox.auth.generic import GenericAuthHandler
from inbox.basicauth import UserRecoverableConfigError


class MockIMAPClient(IMAPClient):

    def __init__(self):
        super(MockIMAPClient, self).__init__('randomhost')

    def _create_IMAP4(self):
        return Mock()

    def logout(self):
        pass


def test_imap_not_fully_enabled(monkeypatch):

    def folder_list_fail(conn):
        raise Exception("LIST failed: '[ALERT] full IMAP support "
                        "is NOT enabled for this account'")

    monkeypatch.setattr('imapclient.IMAPClient.list_folders',
                        folder_list_fail)

    def fake_connect(email, credential, imap_endpoint):
        return MockIMAPClient()

    response = {
        'email': 'test@test.com',
        'password': 'test123',
        'imap_server_host': '0.0.0.0',
        'imap_server_port': 22,
        'smtp_server_host': '0.0.0.0',
        'smtp_server_port': 23
    }

    with session_scope() as db_session:
        handler = GenericAuthHandler('custom')
        acct = handler.create_account(
            db_session,
            'test@test.com',
            response)
        handler.connect_account = fake_connect
        handler._supports_condstore = lambda x: True
        with pytest.raises(UserRecoverableConfigError):
            verified = handler.verify_account(acct)
            assert verified is not True
