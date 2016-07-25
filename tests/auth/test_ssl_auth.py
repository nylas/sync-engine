import copy

import pytest
from imapclient import IMAPClient

from inbox.auth.generic import GenericAuthHandler, create_imap_connection
from inbox.sendmail.base import SendMailException
from inbox.sendmail.smtp.postel import SMTPClient
from inbox.basicauth import SSLNotSupportedError


settings = [
    {
        'provider': 'custom',
        'settings': {
            'name': 'MyAOL',
            'email': 'benbitdit@aol.com',
            'imap_server_host': 'imap.aol.com',
            'imap_server_port': 143,
            'imap_username': 'benbitdit@aol.com',
            'imap_password': 'IHate2Gmail',
            'smtp_server_host': 'smtp.aol.com',
            'smtp_server_port': 587,
            'smtp_username': 'benbitdit@aol.com',
            'smtp_password': 'IHate2Gmail',
            'ssl_required': True
        }
    },
    {
        'provider': 'custom',
        'settings': {
            'name': 'Test',
            'email': 'test@tivertical.com',
            'imap_server_host': 'tivertical.com',
            'imap_server_port': 143,
            'imap_username': 'test@tivertical.com',
            'imap_password': 'testpwd',
            'smtp_server_host': 'tivertical.com',
            'smtp_server_port': 587,
            'smtp_username': 'test@tivertical.com',
            'smtp_password': 'testpwd',
            'ssl_required': False
        }
    }
]


def _create_account(settings, ssl):
    email = settings['settings']['email']
    handler = GenericAuthHandler(settings['provider'])
    credentials = copy.deepcopy(settings)
    credentials['settings']['ssl_required'] = ssl
    account = handler.create_account(email, credentials['settings'])
    return account


def test_account_ssl_required():
    for ssl in (True, False):
        account = _create_account(settings[0], ssl)
        assert account.ssl_required == ssl


@pytest.mark.parametrize('settings', settings)
@pytest.mark.networkrequired
def test_imap_connection(settings):
    host = settings['settings']['imap_server_host']
    port = settings['settings']['imap_server_port']

    conn = IMAPClient(host, port=port, use_uid=True, ssl=False, timeout=120)

    if conn.has_capability('STARTTLS'):
        conn = create_imap_connection(host, port, ssl_required=True)
        conn.login(settings['settings']['imap_username'],
                   settings['settings']['imap_password'])
    else:
        with pytest.raises(SSLNotSupportedError):
            create_imap_connection(host, port, ssl_required=True)
        conn = create_imap_connection(host, port, ssl_required=False)
        conn.login(settings['settings']['imap_username'],
                   settings['settings']['imap_password'])


@pytest.mark.parametrize('settings', settings)
@pytest.mark.networkrequired
def test_smtp_connection(settings):
    has_starttls = ('aol' in settings['settings']['smtp_server_host'])

    if has_starttls:
        account = _create_account(settings, ssl=True)
        smtp_client = SMTPClient(account)
        with smtp_client._get_connection():
            pass
    else:
        account = _create_account(settings, ssl=True)
        smtp_client = SMTPClient(account)
        with pytest.raises(SendMailException):
            with smtp_client._get_connection():
                pass
        account = _create_account(settings, ssl=False)
        smtp_client = SMTPClient(account)
        with smtp_client._get_connection():
            pass


@pytest.mark.parametrize('settings', settings)
@pytest.mark.networkrequired
def test_auth(settings):
    handler = GenericAuthHandler(settings['provider'])

    has_starttls = ('aol' in settings['settings']['imap_server_host'])
    if has_starttls:
        account = _create_account(settings, ssl=True)
        handler.verify_account(account)
    else:
        account = _create_account(settings, ssl=True)
        with pytest.raises(Exception):
            handler.verify_account(account)
        account = _create_account(settings, ssl=False)
        handler.verify_account(account)
