import copy

import pytest

from inbox.models.account import Account
from inbox.auth.generic import GenericAuthHandler
from inbox.basicauth import UserRecoverableConfigError, ValidationError


settings = {
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
        'smtp_password': 'IHate2Gmail'
    }
}


def test_create_account(db):
    email = settings['settings']['email']
    imap_host = settings['settings']['imap_server_host']
    imap_port = settings['settings']['imap_server_port']
    smtp_host = settings['settings']['smtp_server_host']
    smtp_port = settings['settings']['smtp_server_port']

    handler = GenericAuthHandler(settings['provider'])

    # Create an authenticated account
    account = handler.create_account(email, settings['settings'])
    db.session.add(account)
    db.session.commit()
    # Verify its settings
    id_ = account.id
    account = db.session.query(Account).get(id_)
    assert account.imap_endpoint == (imap_host, imap_port)
    assert account.smtp_endpoint == (smtp_host, smtp_port)


def test_update_account(db):
    email = settings['settings']['email']
    imap_host = settings['settings']['imap_server_host']
    imap_port = settings['settings']['imap_server_port']
    smtp_host = settings['settings']['smtp_server_host']
    smtp_port = settings['settings']['smtp_server_port']

    handler = GenericAuthHandler(settings['provider'])

    # Create an authenticated account
    account = handler.create_account(email, settings['settings'])
    db.session.add(account)
    db.session.commit()
    id_ = account.id

    # A valid update
    updated_settings = copy.deepcopy(settings)
    updated_settings['settings']['name'] = 'Neu!'
    account = handler.update_account(account, updated_settings['settings'])
    db.session.add(account)
    db.session.commit()
    account = db.session.query(Account).get(id_)
    assert account.name == 'Neu!'

    # Invalid updates
    for (attr, value, updated_settings) in generate_endpoint_updates(settings):
        assert value in updated_settings['settings'].values()
        with pytest.raises(UserRecoverableConfigError):
            account = handler.update_account(account, updated_settings['settings'])
        db.session.add(account)
        db.session.commit()

        account = db.session.query(Account).get(id_)
        assert getattr(account, attr) != value
        assert account.imap_endpoint == (imap_host, imap_port)
        assert account.smtp_endpoint == (smtp_host, smtp_port)


def test_double_auth(db):
    settings = {
        'provider': 'yahoo',
        'settings': {
            'name': 'Y.Y!',
            'locale': 'fr',
            'email': 'cypresstest@yahoo.com',
            'password': 'IHate2Gmail'}
    }
    email = settings['settings']['email']
    password = settings['settings']['password']

    handler = GenericAuthHandler(settings['provider'])

    # First authentication, using a valid password, succeeds.
    valid_settings = copy.deepcopy(settings)

    account = handler.create_account(email, valid_settings['settings'])
    assert handler.verify_account(account) is True

    db.session.add(account)
    db.session.commit()
    id_ = account.id
    account = db.session.query(Account).get(id_)
    assert account.email_address == email
    assert account.imap_username == email
    assert account.smtp_username == email
    assert account.password == password
    assert account.imap_password == password
    assert account.smtp_password == password

    # Second auth using an invalid password should fail.
    invalid_settings = copy.deepcopy(settings)
    invalid_settings['settings']['password'] = 'invalid_password'
    with pytest.raises(ValidationError):
        account = handler.update_account(account, invalid_settings['settings'])
        handler.verify_account(account)

    db.session.expire(account)

    # Ensure original account is unaffected
    account = db.session.query(Account).get(id_)
    assert account.email_address == email
    assert account.imap_username == email
    assert account.smtp_username == email
    assert account.password == password
    assert account.imap_password == password
    assert account.smtp_password == password


def generate_endpoint_updates(settings):
    for key in ('imap_server_host', 'smtp_server_host'):
        attr = '_{}'.format(key)
        value = 'I.am.Malicious.{}'.format(key)
        updated_settings = copy.deepcopy(settings)
        updated_settings['settings'][key] = value
        yield (attr, value, updated_settings)
