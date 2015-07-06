# -*- coding: UTF-8 -*-
from inbox.auth.gmail import GmailAuthHandler


def test_create_account(db):

    # setup
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
    first_auth_args = {
        'refresh_token': token_1,
        'scope': scopes_1,
        'client_id': client_id_1,
        'client_secret': client_secret_1
    }
    resp.update(first_auth_args)

    account = g.create_account(db.session, email, resp)
    db.session.add(account)
    db.session.commit()

    assert len(account.auth_credentials) == 1

    auth_creds = account.auth_credentials[0]
    assert auth_creds.client_id == client_id_1
    assert auth_creds.client_secret == client_secret_1
    assert auth_creds.scopes == scopes_1
    assert auth_creds.refresh_token == token_1

    # Auth me twice...
    token_2 = 'second_token_!!'
    client_id_2 = 'second client id'
    client_secret_2 = 'secodn client secret'
    scopes_2 = 'scope scop sco sc s'
    second_auth_args = {
        'refresh_token': token_2,
        'scope': scopes_2,
        'client_id': client_id_2,
        'client_secret': client_secret_2
    }
    resp.update(second_auth_args)

    account = g.create_account(db.session, email, resp)
    db.session.add(account)
    db.session.commit()

    assert len(account.auth_credentials) == 2

    auth_creds = next((creds for creds in account.auth_credentials
                      if creds.refresh_token == token_2), False)
    assert auth_creds
    assert auth_creds.client_id == client_id_2
    assert auth_creds.client_secret == client_secret_2
    assert auth_creds.scopes == scopes_2

    # Don't add duplicate row in GmailAuthCredentials if we get same
    # refresh_token back
    resp.update(first_auth_args)
    account = g.create_account(db.session, email, resp)
    db.session.add(account)
    db.session.commit()

    assert len(account.auth_credentials) == 2
