"""Test that the All Mail folder is enabled for Gmail.
"""

import pytest

from inbox.auth.gmail import GmailAuthHandler
from inbox.crispin import GmailCrispinClient, GmailSettingError


class AccountStub(object):
    id = 0
    email_address = 'bob@bob.com'
    access_token = None
    imap_endpoint = None

    def new_token(self):
        return ('foo', 22)

    def validate_token(self, new_token):
        return True


class ConnectionStub(object):
    def logout(self):
        pass


def get_auth_handler(monkeypatch, folders):
    g = GmailAuthHandler('gmail')

    def mock_connect(x, y, z, a=None):
        return ConnectionStub()

    g.connect_account = mock_connect
    monkeypatch.setattr(GmailCrispinClient, 'folder_names',
                        lambda x: folders)
    return g


def test_all_mail_missing(monkeypatch):
    """Test that validate_folders throws a GmailSettingError if All Mail
       is not in the list of folders.
    """
    g = get_auth_handler(monkeypatch, {'inbox': 'INBOX'})

    with pytest.raises(GmailSettingError):
        g.verify_config(AccountStub())


def test_all_mail_present(monkeypatch):
    """Test that the validate_folders passes if All Mail is present.
    """
    g = get_auth_handler(monkeypatch, {'all': 'ALL', 'inbox': 'INBOX',
                                       'trash': 'TRASH'})

    assert g.verify_config(AccountStub())


def test_trash_missing(monkeypatch):
    g = get_auth_handler(monkeypatch, {'inbox': 'INBOX', 'all': 'ALL'})

    with pytest.raises(GmailSettingError):
        g.verify_config(AccountStub())
