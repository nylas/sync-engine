# -*- coding: UTF-8 -*-
import pytest

from inbox.auth.gmail import create_account
from inbox.models.backends.gmail import GmailAccount
from inbox.models.secret import Secret

ACCOUNT_ID = 1


def test_secret(db, config):
    """
    Ensure secrets are encrypted.
    Ensure secret are decrypted correctly on retrieval.
    Ensure secrets are bytes.

    """
    bytes_secret = b'\xff\x00\xf1'
    unicode_secret = u'foo\u00a0'

    secret = Secret()
    secret.type = 'password'
    secret.secret = bytes_secret

    db.session.add(secret)
    db.session.commit()

    secret = db.session.query(Secret).get(secret.id)

    assert secret._secret != bytes_secret, 'secret is not encrypted'
    assert secret.secret == bytes_secret, 'secret not decrypted correctly'

    with pytest.raises(TypeError) as e:
        secret.secret = unicode_secret

    assert e.typename == 'TypeError', 'secret cannot be unicode'


def test_token(db, config):
    """
    Ensure tokens are encrypted.
    Ensure tokens are decrypted correctly on retrieval.
    Ensure tokens are not leaked.

    Note: This tests refresh_tokens but passwords work in the same way

    """
    token = 'tH*$&123abcº™™∞'

    email = 'vault.test@localhost.com'
    resp = {'access_token': '',
            'expires_in': 3600,
            'refresh_token': token,
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
    account = create_account(db.session, email, resp)

    db.session.add(account)
    db.session.commit()

    secret_id = account.refresh_token_id
    secret = db.session.query(Secret).get(secret_id)

    assert secret._secret != token, 'token not encrypted'

    decrypted_secret = secret.secret
    assert decrypted_secret == token and \
        account.refresh_token == decrypted_secret, \
        'token not decrypted correctly'

    db.session.delete(account)
    db.session.commit()

    account = db.session.query(GmailAccount).filter_by(
        email_address=email).scalar()
    assert not account

    secret = db.session.query(Secret).filter(Secret.id == secret_id).scalar()
    assert not secret, 'token not deleted on account deletion'


def test_token_inputs(db, config):
    """
    Ensure unicode tokens are converted to bytes.
    Ensure invalid UTF-8 tokens are handled correctly.

    """
    # Unicode
    unicode_token = u'myunicodesecret'

    # Invalid UTF-8 byte sequence
    invalid_token = b'\xff\x10'

    # NULL byte
    null_token = b'\x1f\x00\xf1'

    account = db.session.query(GmailAccount).get(ACCOUNT_ID)

    account.refresh_token = unicode_token

    secret_id = account.refresh_token_id
    secret = db.session.query(Secret).get(secret_id)

    assert not isinstance(secret.secret, unicode), 'secret cannot be unicode'
    assert secret.secret == unicode_token, 'token not decrypted correctly'

    with pytest.raises(ValueError) as e:
        account.refresh_token = invalid_token

    assert e.typename == 'ValueError', 'token cannot be invalid UTF-8'

    with pytest.raises(ValueError) as f:
        account.refresh_token = null_token

    assert f.typename == 'ValueError', 'token cannot contain NULL byte'

    assert account.refresh_token == unicode_token
