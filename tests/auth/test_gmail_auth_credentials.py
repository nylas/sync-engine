# -*- coding: UTF-8 -*-
import pytest
from sqlalchemy.orm import joinedload, object_session

from inbox.auth.gmail import GmailAuthHandler
from inbox.models.session import session_scope
from inbox.models.account import Account
from inbox.models.backends.gmail import (GOOGLE_CALENDAR_SCOPE,
                                         GOOGLE_CONTACTS_SCOPE,
                                         GOOGLE_EMAIL_SCOPE,
                                         GmailAccount)
from inbox.auth.gmail import g_token_manager
from inbox.basicauth import OAuthError, ConnectionError

SHARD_ID = 0
ACCESS_TOKEN = 'this_is_an_access_token'


@pytest.fixture
def account_with_multiple_auth_creds(db):
    email = 'test_account@localhost.com'
    resp = {'access_token': '',
            'expires_in': 3600,
            'email': email,
            'family_name': '',
            'given_name': '',
            'name': '',
            'gender': '',
            'id': 0,
            'user_id': '',
            'id_token': '',
            'link': 'http://example.com',
            'locale': '',
            'picture': '',
            'hd': ''}

    all_scopes = ' '.join(
        [GOOGLE_CALENDAR_SCOPE, GOOGLE_CONTACTS_SCOPE, GOOGLE_EMAIL_SCOPE])

    first_auth_args = {
        'refresh_token': 'refresh_token_1',
        'client_id': 'client_id_1',
        'client_secret': 'client_secret_1',
        'scope': all_scopes,
        'sync_contacts': True,
        'sync_events': True
    }

    second_auth_args = {
        'refresh_token': 'refresh_token_2',
        'client_id': 'client_id_2',
        'client_secret': 'client_secret_2',
        'scope': GOOGLE_EMAIL_SCOPE,
        'sync_contacts': False,
        'sync_events': False
    }

    g = GmailAuthHandler('gmail')
    g.verify_config = lambda x: True

    resp.update(first_auth_args)
    account = g.get_account(SHARD_ID, email, resp)
    db.session.add(account)
    db.session.commit()

    resp.update(second_auth_args)
    account = g.get_account(SHARD_ID, email, resp)
    db.session.add(account)
    db.session.commit()

    return account


@pytest.fixture
def account_with_single_auth_creds(db):
    email = 'test_account2@localhost.com'
    resp = {'access_token': '',
            'expires_in': 3600,
            'email': email,
            'family_name': '',
            'given_name': '',
            'name': '',
            'gender': '',
            'id': 0,
            'user_id': '',
            'id_token': '',
            'link': 'http://example.com',
            'locale': '',
            'picture': '',
            'hd': '',
            'refresh_token': 'refresh_token_3',
            'client_id': 'client_id_1',
            'client_secret': 'client_secret_1',
            'scope': ' '.join([GOOGLE_CALENDAR_SCOPE, GOOGLE_EMAIL_SCOPE]),
            'sync_contacts': False,
            'sync_events': True
            }

    g = GmailAuthHandler('gmail')
    g.verify_config = lambda x: True

    account = g.get_account(SHARD_ID, email, resp)
    db.session.add(account)
    db.session.commit()

    return account


@pytest.fixture
def patch_access_token_getter(monkeypatch):
    class TokenGenerator:
        def __init__(self):
            self.revoked_refresh_tokens = []
            self.connection_error_tokens = []

        def new_token(self, refresh_token, client_id=None, client_secret=None):
            if refresh_token in self.connection_error_tokens:
                raise ConnectionError("Invalid connection!")
            if refresh_token in self.revoked_refresh_tokens:
                raise OAuthError("Invalid token")
            expires_in = 10000
            return ACCESS_TOKEN, expires_in

        def revoke_refresh_token(self, refresh_token):
            self.revoked_refresh_tokens.append(refresh_token)

        def force_connection_errors(self, refresh_token):
            self.connection_error_tokens.append(refresh_token)

    token_generator = TokenGenerator()
    monkeypatch.setattr('inbox.auth.oauth.OAuthAuthHandler.new_token',
                        token_generator.new_token)
    return token_generator


def test_auth_revoke(
        db, account_with_multiple_auth_creds, patch_access_token_getter):
    account = account_with_multiple_auth_creds
    refresh_token1 = account.auth_credentials[0].refresh_token
    refresh_token2 = account.auth_credentials[1].refresh_token

    assert len(account.auth_credentials) == 2
    assert len(account.valid_auth_credentials) == 2
    assert account.sync_contacts is True
    assert account.sync_events is True
    assert account.sync_state != 'invalid'
    assert account.sync_should_run is True

    patch_access_token_getter.revoke_refresh_token(refresh_token1)
    with pytest.raises(OAuthError):
        account.new_token(GOOGLE_CONTACTS_SCOPE)
    assert account.new_token(GOOGLE_EMAIL_SCOPE).value == ACCESS_TOKEN
    with pytest.raises(OAuthError):
        account.new_token(GOOGLE_CALENDAR_SCOPE)

    account.verify_all_credentials()
    assert len(account.auth_credentials) == 2
    assert len(account.valid_auth_credentials) == 1
    assert account.sync_contacts is False
    assert account.sync_events is False
    assert account.sync_state != 'invalid'
    assert account.sync_should_run is True

    patch_access_token_getter.revoke_refresh_token(refresh_token2)
    with pytest.raises(OAuthError):
        account.new_token(GOOGLE_CONTACTS_SCOPE)
    with pytest.raises(OAuthError):
        account.new_token(GOOGLE_EMAIL_SCOPE)
    with pytest.raises(OAuthError):
        account.new_token(GOOGLE_CALENDAR_SCOPE)

    account.verify_all_credentials()
    assert len(account.auth_credentials) == 2
    assert len(account.valid_auth_credentials) == 0
    assert account.sync_state == 'invalid'
    assert account.sync_should_run is False


def test_auth_revoke_different_order(
        db, account_with_multiple_auth_creds, patch_access_token_getter):
    account = account_with_multiple_auth_creds
    refresh_token1 = account.auth_credentials[0].refresh_token
    refresh_token2 = account.auth_credentials[1].refresh_token

    assert len(account.auth_credentials) == 2
    assert len(account.valid_auth_credentials) == 2
    assert account.sync_contacts is True
    assert account.sync_events is True
    assert account.sync_state != 'invalid'
    assert account.sync_should_run is True

    patch_access_token_getter.revoke_refresh_token(refresh_token2)
    assert account.new_token(GOOGLE_EMAIL_SCOPE).value == ACCESS_TOKEN
    assert account.new_token(GOOGLE_CONTACTS_SCOPE).value == ACCESS_TOKEN
    assert account.new_token(GOOGLE_CALENDAR_SCOPE).value == ACCESS_TOKEN

    account.verify_all_credentials()
    assert len(account.auth_credentials) == 2
    assert account.sync_contacts is True
    assert account.sync_events is True
    assert account.sync_state != 'invalid'
    assert account.sync_should_run is True
    assert len(account.valid_auth_credentials) == 1

    patch_access_token_getter.revoke_refresh_token(refresh_token1)
    with pytest.raises(OAuthError):
        account.new_token(GOOGLE_CONTACTS_SCOPE)
    with pytest.raises(OAuthError):
        account.new_token(GOOGLE_EMAIL_SCOPE)
    with pytest.raises(OAuthError):
        account.new_token(GOOGLE_CALENDAR_SCOPE)

    account.verify_all_credentials()
    assert len(account.auth_credentials) == 2
    assert len(account.valid_auth_credentials) == 0
    assert account.sync_contacts is False
    assert account.sync_events is False
    assert account.sync_state == 'invalid'
    assert account.sync_should_run is False


def test_create_account(db):
    email = 'vault.test@localhost.com'
    resp = {'access_token': '',
            'expires_in': 3600,
            'email': email,
            'family_name': '',
            'given_name': '',
            'name': '',
            'gender': '',
            'id': 0,
            'user_id': '',
            'id_token': '',
            'link': 'http://example.com',
            'locale': '',
            'picture': '',
            'hd': ''}

    g = GmailAuthHandler('gmail')
    g.verify_config = lambda x: True

    # Auth me once...
    token_1 = 'the_first_token'
    client_id_1 = 'first client id'
    client_secret_1 = 'first client secret'
    scopes_1 = 'scope scop sco sc s'
    scopes_1_list = scopes_1.split(' ')
    first_auth_args = {
        'refresh_token': token_1,
        'scope': scopes_1,
        'client_id': client_id_1,
        'client_secret': client_secret_1
    }
    resp.update(first_auth_args)

    account = g.create_account(email, resp)
    db.session.add(account)
    db.session.commit()
    account_id = account.id

    with session_scope(account_id) as db_session:
        account = db_session.query(Account).filter(
            Account.email_address == email).one()

        assert account.id == account_id
        assert isinstance(account, GmailAccount)

        assert len(account.auth_credentials) == 1
        auth_creds = account.auth_credentials[0]
        assert auth_creds.client_id == client_id_1
        assert auth_creds.client_secret == client_secret_1
        assert auth_creds.scopes == scopes_1_list
        assert auth_creds.refresh_token == token_1


def test_get_account(db):
    email = 'vault.test@localhost.com'
    resp = {'access_token': '',
            'expires_in': 3600,
            'email': email,
            'family_name': '',
            'given_name': '',
            'name': '',
            'gender': '',
            'id': 0,
            'user_id': '',
            'id_token': '',
            'link': 'http://example.com',
            'locale': '',
            'picture': '',
            'hd': ''}

    g = GmailAuthHandler('gmail')
    g.verify_config = lambda x: True

    # Auth me once...
    token_1 = 'the_first_token'
    client_id_1 = 'first client id'
    client_secret_1 = 'first client secret'
    scopes_1 = 'scope scop sco sc s'
    scopes_1_list = scopes_1.split(' ')
    first_auth_args = {
        'refresh_token': token_1,
        'scope': scopes_1,
        'client_id': client_id_1,
        'client_secret': client_secret_1
    }
    resp.update(first_auth_args)

    account = g.get_account(SHARD_ID, email, resp)
    db.session.add(account)
    db.session.commit()

    db.session.refresh(account)
    assert len(account.auth_credentials) == 1
    auth_creds = account.auth_credentials[0]
    assert auth_creds.client_id == client_id_1
    assert auth_creds.client_secret == client_secret_1
    assert auth_creds.scopes == scopes_1_list
    assert auth_creds.refresh_token == token_1

    # Auth me twice...
    token_2 = 'second_token_!'
    client_id_2 = 'second client id'
    client_secret_2 = 'second client secret'
    scopes_2 = 'scope scop sco sc s'
    scopes_2_list = scopes_2.split(' ')
    second_auth_args = {
        'refresh_token': token_2,
        'scope': scopes_2,
        'client_id': client_id_2,
        'client_secret': client_secret_2
    }
    resp.update(second_auth_args)

    account = g.get_account(SHARD_ID, email, resp)
    db.session.merge(account)
    db.session.commit()

    assert len(account.auth_credentials) == 2
    auth_creds = next((creds for creds in account.auth_credentials
                       if creds.refresh_token == token_2), False)
    assert auth_creds
    assert auth_creds.client_id == client_id_2
    assert auth_creds.client_secret == client_secret_2
    assert auth_creds.scopes == scopes_2_list

    # Don't add duplicate row in GmailAuthCredentials for the same
    # client_id/client_secret pair.
    resp.update(first_auth_args)
    resp['refresh_token'] = 'a new refresh token'
    account = g.get_account(SHARD_ID, email, resp)
    db.session.merge(account)
    db.session.commit()

    assert len(account.auth_credentials) == 2

    # Should still work okay if we don't get a refresh token back
    del resp['refresh_token']
    account = g.get_account(SHARD_ID, email, resp)
    db.session.merge(account)
    db.session.commit()

    assert len(account.auth_credentials) == 2


def test_g_token_manager(
        db, patch_access_token_getter,
        account_with_multiple_auth_creds,
        account_with_single_auth_creds):
    account = account_with_multiple_auth_creds
    refresh_token1 = account.auth_credentials[0].refresh_token
    refresh_token2 = account.auth_credentials[1].refresh_token
    g_token_manager.clear_cache(account)

    # existing account w/ multiple credentials, all valid
    assert (g_token_manager.get_token(account, GOOGLE_EMAIL_SCOPE) ==
            ACCESS_TOKEN)
    assert (g_token_manager.get_token(account, GOOGLE_CONTACTS_SCOPE) ==
            ACCESS_TOKEN)
    assert (g_token_manager.get_token(account, GOOGLE_CALENDAR_SCOPE) ==
            ACCESS_TOKEN)
    for auth_creds in account.auth_credentials:
        assert auth_creds.is_valid

    # existing account w/ multiple credentials: some valid
    patch_access_token_getter.revoke_refresh_token(refresh_token1)
    g_token_manager.clear_cache(account)

    with pytest.raises(OAuthError):
        g_token_manager.get_token(account, GOOGLE_CONTACTS_SCOPE)

    assert (g_token_manager.get_token(account, GOOGLE_EMAIL_SCOPE) ==
            ACCESS_TOKEN)

    with pytest.raises(OAuthError):
        g_token_manager.get_token(account, GOOGLE_CALENDAR_SCOPE)

    # existing account w/ multiple credentials: all invalid
    patch_access_token_getter.revoke_refresh_token(refresh_token2)
    g_token_manager.clear_cache(account)

    with pytest.raises(OAuthError):
        g_token_manager.get_token(account, GOOGLE_EMAIL_SCOPE)
    with pytest.raises(OAuthError):
        g_token_manager.get_token(account, GOOGLE_CALENDAR_SCOPE)
    with pytest.raises(OAuthError):
        g_token_manager.get_token(account, GOOGLE_CONTACTS_SCOPE)
    db.session.refresh(account)
    for auth_creds in account.auth_credentials:
        assert not auth_creds.is_valid

    # existing account w/ one credential
    account = account_with_single_auth_creds
    g_token_manager.clear_cache(account)

    assert (g_token_manager.get_token(account, GOOGLE_EMAIL_SCOPE) ==
            ACCESS_TOKEN)
    assert (g_token_manager.get_token(account, GOOGLE_CALENDAR_SCOPE) ==
            ACCESS_TOKEN)
    with pytest.raises(OAuthError):
        g_token_manager.get_token(account, GOOGLE_CONTACTS_SCOPE)


def test_new_token_with_non_oauth_error(
        db, patch_access_token_getter, account_with_multiple_auth_creds):
    account = account_with_multiple_auth_creds
    refresh_token1 = account.auth_credentials[0].refresh_token
    refresh_token2 = account.auth_credentials[1].refresh_token
    g_token_manager.clear_cache(account)

    assert account.new_token(GOOGLE_EMAIL_SCOPE).value == ACCESS_TOKEN

    patch_access_token_getter.revoke_refresh_token(refresh_token1)
    patch_access_token_getter.force_connection_errors(refresh_token2)

    with pytest.raises(ConnectionError):
        g_token_manager.get_token(account, GOOGLE_EMAIL_SCOPE)
    db.session.refresh(account)
    assert len(account.valid_auth_credentials) == 1


def test_invalid_token_during_connect(db, patch_access_token_getter,
                                      account_with_single_auth_creds):
    account_id = account_with_single_auth_creds.id

    patch_access_token_getter.revoke_refresh_token(
        account_with_single_auth_creds.auth_credentials[0].refresh_token)
    account_with_single_auth_creds.verify_all_credentials()
    assert len(account_with_single_auth_creds.valid_auth_credentials) == 0
    g_token_manager.clear_cache(account_with_single_auth_creds)

    # connect_account() takes an /expunged/ account object
    # that has the necessary relationships eager-loaded
    object_session(account_with_single_auth_creds).expunge(
        account_with_single_auth_creds)
    assert not object_session(account_with_single_auth_creds)

    account = db.session.query(GmailAccount).options(
        joinedload(GmailAccount.auth_credentials)).get(
        account_id)
    db.session.expunge(account)
    assert not object_session(account)

    g = GmailAuthHandler('gmail')

    with pytest.raises(OAuthError):
        g.connect_account(account)

    invalid_account = db.session.query(GmailAccount).get(account_id)
    for auth_creds in invalid_account.auth_credentials:
        assert not auth_creds.is_valid
