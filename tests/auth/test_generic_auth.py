import copy

import pytest

from inbox.models.account import Account
from inbox.auth.generic import GenericAuthHandler
from inbox.basicauth import UserRecoverableConfigError


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


def generate_endpoint_updates(settings):
    for key in ('imap_server_host', 'smtp_server_host'):
        attr = '_{}'.format(key)
        value = 'I.am.Malicious.{}'.format(key)
        updated_settings = copy.deepcopy(settings)
        updated_settings['settings'][key] = value
        yield (attr, value, updated_settings)
