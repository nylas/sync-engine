"""
Tests which exercise the vault for storing secrets.
"""
from sqlalchemy.orm.exc import NoResultFound

from inbox.models.vault import vault, NotFound
from inbox.auth.gmail import create_account
from inbox.models.backends.gmail import GmailAccount
from time import time


TV = "TEST VALUE"


def test_not_found():
    found = None
    try:
        found = vault.get(-1)
    except NotFound:
        pass

    assert not found


def test_simple():
    """Add, get and remove a test value, make sure value is removed"""
    secret_id = vault.put(TV)
    assert vault.get(secret_id) == TV
    vault.remove(secret_id)

    # Make sure the value is actually removed
    found = None
    try:
        found = vault.get(secret_id)
    except NotFound:
        pass

    assert not found


def test_many():
    """Add and remove many times in a row."""
    start = time()
    for i in range(10):
        secret_id = vault.put(TV)
        assert vault.get(secret_id) == TV
        vault.remove(secret_id)

    print "time: ", time() - start


def test_account(db, config):
    """Creates a fake account, ensuring that the refresh token can be retrieved.
    It also removes the account to ensure that we are not leaking secrets."""

    # Add the account
    email = "vault.test@localhost.com"
    resp = {'access_token': '',
            'expires_in': 3600,
            'refresh_token': TV,
            'scope': '',
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
    account = create_account(db.session, resp)
    db.session.add(account)
    db.session.commit()

    # Check the account
    assert account.refresh_token == TV

    secret_id = account.refresh_token_id
    assert vault.get(secret_id) == TV

    # Make sure updating the account doesn't affect the stored valuet
    account.name = "new_name"
    db.session.add(account)
    db.session.commit()
    assert account.refresh_token == TV

    # Remove the account
    db.session.delete(account)
    db.session.commit()

    # make sure the account was deleted
    found = None
    try:
        found = db.session.query(GmailAccount) \
            .filter_by(email_address=email).one()
    except NoResultFound:
        pass
    assert not found

    # Ensure secrets aren't leaked
    try:
        found = vault.get(secret_id)
    except NotFound:
        pass

    assert not found
