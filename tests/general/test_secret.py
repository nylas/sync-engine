# -*- coding: UTF-8 -*-
import pytest

from inbox.auth.gmail import create_account
from inbox.models.backends.gmail import GmailAccount
from inbox.models.secret import Secret

ACCOUNT_ID = 1


@pytest.mark.parametrize('encrypt', [True, False])
def test_secret(db, config, encrypt):
    """
    If encryption is enabled, ensure that:
    * secrets are encrypted.
    * secrets are decrypted correctly on retrieval.
    * secrets are bytes.
    """
    config['ENCRYPT_SECRETS'] = encrypt
    bytes_secret = b'\xff\x00\xf1'
    unicode_secret = u'foo\u00a0'

    secret = Secret()
    secret.type = 'password'
    secret.secret = bytes_secret

    db.session.add(secret)
    db.session.commit()

    secret = db.session.query(Secret).get(secret.id)

    if encrypt:
        assert secret._secret != bytes_secret, 'secret is not encrypted'
    else:
        assert secret._secret == bytes_secret
    assert secret.secret == bytes_secret, 'secret not decrypted correctly'

    with pytest.raises(TypeError) as e:
        secret.secret = unicode_secret

    assert e.typename == 'TypeError', 'secret cannot be unicode'


@pytest.mark.parametrize('encrypt', [True, False])
def test_token(db, config, encrypt):
    """
    If encryption is enabled, ensure that:
    * tokens are encrypted.
    * tokens are decrypted correctly on retrieval.

    Note: This tests refresh_tokens but passwords work in the same way

    """
    config['ENCRYPT_SECRETS'] = encrypt
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

    assert secret == account.secret

    if encrypt:
        assert secret._secret != token, 'token not encrypted'
    else:
        assert secret._secret == token, 'token encrypted when encryption disabled'

    decrypted_secret = secret.secret
    assert decrypted_secret == token and \
        account.refresh_token == decrypted_secret, \
        'token not decrypted correctly'


@pytest.mark.parametrize('encrypt', [True, False])
def test_token_inputs(db, config, encrypt):
    """
    Ensure unicode tokens are converted to bytes.
    Ensure invalid UTF-8 tokens are handled correctly.

    """
    config['ENCRYPT_SECRETS'] = encrypt
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
