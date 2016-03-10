# -*- coding: utf-8 -*-
import copy
import socket

import pytest

from inbox.util.url import parent_domain
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


def test_update_account_with_different_subdomain(db, monkeypatch):
    # Check that you can update the server endpoints for an account
    # provided that
    # 1/ they're on a subdomain of the same domain name.
    # 2/ they have the same IP address.
    #
    # To test this we use Microsoft's Office365 setup, which
    # has mail.office365.com and outlook.office365.com point to
    # the same address.
    email = settings['settings']['email']
    settings['settings']['imap_server_host'] = 'outlook.office365.com'
    settings['settings']['smtp_server_host'] = 'outlook.office365.com'

    handler = GenericAuthHandler(settings['provider'])

    # Create an authenticated account
    account = handler.create_account(email, settings['settings'])
    db.session.add(account)
    db.session.commit()
    id_ = account.id

    def gethostbyname_patch(x):
        return "127.0.0.1"

    monkeypatch.setattr(socket, 'gethostbyname', gethostbyname_patch)

    # A valid update
    updated_settings = copy.deepcopy(settings)
    updated_settings['settings']['imap_server_host'] = 'mail.office365.com'
    updated_settings['settings']['smtp_server_host'] = 'mail.office365.com'
    updated_settings['settings']['name'] = 'Neu!'
    account = handler.update_account(account, updated_settings['settings'])
    db.session.add(account)
    db.session.commit()
    account = db.session.query(Account).get(id_)
    assert account.name == 'Neu!'
    assert account._imap_server_host == 'mail.office365.com'
    assert account._smtp_server_host == 'mail.office365.com'


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


def test_parent_domain():
    assert parent_domain('x.a.com') == 'a.com'
    assert parent_domain('a.com') == 'a.com'
    assert parent_domain('.com') == ''
    assert parent_domain('test.google.com') == 'google.com'

    assert parent_domain('smtp.example.a.com') == parent_domain('imap.example.a.com')
    assert parent_domain('smtp.example.a.com') == parent_domain('imap.a.com')

    assert parent_domain('company.co.uk') != parent_domain('evilcompany.co.uk')


def test_successful_reauth_resets_sync_state(db):
    settings = {
        'provider': 'yahoo',
        'settings': {
            'name': 'Y.Y!',
            'locale': 'fr',
            'email': 'cypresstest@yahoo.com',
            'password': 'IHate2Gmail'}
    }
    email = settings['settings']['email']
    handler = GenericAuthHandler(settings['provider'])

    account = handler.create_account(email, settings['settings'])
    assert handler.verify_account(account) is True
    # Brand new accounts have `sync_state`=None.
    assert account.sync_state is None
    db.session.add(account)
    db.session.commit()

    # Pretend account sync starts, and subsequently the password changes,
    # causing the account to be in `sync_state`='invalid'.
    account.mark_invalid()
    db.session.commit()
    assert account.sync_state == 'invalid'

    # Verify the `sync_state` is reset to 'running' on a successful "re-auth".
    account = handler.update_account(account, settings['settings'])
    assert handler.verify_account(account) is True
    assert account.sync_state == 'running'
    db.session.add(account)
    db.session.commit()


def generate_endpoint_updates(settings):
    for key in ('imap_server_host', 'smtp_server_host'):
        attr = '_{}'.format(key)
        value = 'I.am.Malicious.{}'.format(key)
        updated_settings = copy.deepcopy(settings)
        updated_settings['settings'][key] = value
        yield (attr, value, updated_settings)
