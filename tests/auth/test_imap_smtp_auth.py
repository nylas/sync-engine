import pytest

from inbox.auth.generic import GenericAuthHandler
from inbox.basicauth import ValidationError

creds = [
    {
        'provider': 'yahoo',
        'settings': {
            'name': 'Y.Y!',
            'locale': 'fr',
            'email': 'cypresstest@yahoo.com',
            'password': 'IHate2Gmail'}
    },
    {
        'provider': 'custom',
        'settings': {
            'name': 'MyAOL',
            'email': 'benbitdit@aol.com',
            'imap_server_host': 'imap.aol.com',
            'imap_server_port': 993,
            'imap_username': 'benbitdit@aol.com',
            'imap_password': 'IHate2Gmail',
            'smtp_server_host': 'smtp.aol.com',
            'smtp_server_port': 587,
            'smtp_username': 'benbitdit@aol.com',
            'smtp_password': 'IHate2Gmail'
        }
    },
    {
        'provider': 'custom',
        'settings': {
            'name': 'Nylas',
            'email': 'nylastest@runbox.com',
            'imap_server_host': 'mail.runbox.com',
            'imap_server_port': 993,
            'imap_username': 'nylastest',
            'imap_password': 'IHate2Gmail!',
            'smtp_server_host': 'mail.runbox.com',
            'smtp_server_port': 587,
            'smtp_username': 'nylastest',
            'smtp_password': 'IHate2Gmail!'
        }
    }
]


@pytest.mark.parametrize('creds', creds)
@pytest.mark.usefixtures('mock_smtp_get_connection')
def test_auth(creds, mock_auth_imapclient):
    imap_username = creds['settings'].get('imap_username')
    if imap_username is None:
        imap_username = creds['settings']['email']
    imap_password = creds['settings'].get('imap_password')
    if imap_password is None:
        imap_password = creds['settings']['password']
    mock_auth_imapclient._add_login(imap_username, imap_password)

    handler = GenericAuthHandler(creds['provider'])
    email = creds['settings']['email']
    account = handler.create_account(email, creds['settings'])

    # Test that the account was successfully created by the handler.
    assert account.imap_password == imap_password
    if 'smtp_password' in creds['settings']:
        assert account.smtp_password == creds['settings']['smtp_password']
    else:
        assert account.imap_password == creds['settings']['password']
        assert account.smtp_password == creds['settings']['password']

    # Test that the account is valid.
    assert handler.verify_account(account) is True

    # Test that the password can be updated...
    bad_creds = {'email': creds['settings']['email'],
                 'imap_password': 'bad_password',
                 'imap_server_host': creds['settings'].get('imap_server_host'),
                 'imap_server_port': 993,
                 'smtp_server_host': creds['settings'].get('smtp_server_host'),
                 'smtp_server_port': 587
                 }
    handler.update_account(account, bad_creds)
    assert account.imap_password == 'bad_password'
    # ...but logging in again won't work.
    with pytest.raises(ValidationError):
        handler.verify_account(account)
