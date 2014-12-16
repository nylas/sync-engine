"""
Generic OAuth class that provides abstraction for access and
refresh tokens.
"""
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declared_attr

from inbox.models.secret import Secret
from inbox.basicauth import (AuthError, ConnectionError,
                             OAuthInvalidGrantError, OAuthValidationError,
                             OAuthError)
from inbox.log import get_logger
log = get_logger()

__volatile_tokens__ = {}


class OAuthAccount(object):
    # Secret
    @declared_attr
    def refresh_token_id(cls):
        return Column(Integer, ForeignKey(Secret.id), nullable=False)

    @declared_attr
    def secret(cls):
        return relationship('Secret', uselist=False)

    @property
    def refresh_token(self):
        return self.secret.secret

    @refresh_token.setter
    def refresh_token(self, value):
        # Must be a valid UTF-8 byte sequence without NULL bytes.
        if isinstance(value, unicode):
            value = value.encode('utf-8')

        try:
            unicode(value, 'utf-8')
        except UnicodeDecodeError:
            raise ValueError('Invalid refresh_token')

        if b'\x00' in value:
            raise ValueError('Invalid refresh_token')

        if not self.secret:
            self.secret = Secret()

        self.secret.secret = value
        self.secret.type = 'token'

    @property
    def access_token(self):
        if self.id in __volatile_tokens__:
            tok, expires = __volatile_tokens__[self.id]
            if datetime.utcnow() > expires:
                # Remove access token from pool,  return new one
                del __volatile_tokens__[self.id]
                return self.access_token
            else:
                return tok
        else:
            # first time getting access token, or perhaps it expired?
            tok, expires = self._new_token()

            self._validate_token(tok)
            self.set_access_token(tok, expires)
            return tok

    @property
    def access_expiry(self):
        if self.id in __volatile_tokens__:
            tok, expires = __volatile_tokens__[self.id]
            return expires
        else:
            self.access_token
            tok, expires = __volatile_tokens__[self.id]
            return expires

    def renew_access_token(self):
        del __volatile_tokens__[self.id]
        return self.access_token

    def verify(self):
        if self.id in __volatile_tokens__:
            tok, expires = __volatile_tokens__[self.id]

            if datetime.utcnow() > expires:
                del __volatile_tokens__[self.id]
                return self.verify()
            else:
                try:
                    return self._validate_token(tok)
                except AuthError:
                    del __volatile_tokens__[self.id]
                    raise

        else:
            tok, expires = self._new_token()
            valid = self._validate_token(tok)
            self.set_access_token(tok, expires)
            return valid

    def set_access_token(self, tok, expires_in):
        # Subtract 10 seconds as it takes _some_ time to propagate between
        # google's servers and this code (much less than 10 seconds, but
        # 10 should be safe)
        expires = datetime.utcnow() + timedelta(seconds=expires_in - 10)
        if datetime.utcnow() > expires:
            log.error(u"Error setting expired access_token for {}"
                      .format(self.id))
            return

        __volatile_tokens__[self.id] = tok, expires

    def _validate_token(self, tok):
        try:
            return self.auth_handler.validate_token(tok)
        except ConnectionError as e:
            log.error('ConnectionError',
                      message=u"Error while validating access token: {}"
                              .format(e),
                      account_id=self.id)
            raise
        except OAuthValidationError as e:
            log.error('ValidationError',
                      message=u"Error while validating access token: {}"
                              .format(e),
                      account_id=self.id)
            raise

    def _new_token(self):
        try:
            return self.auth_handler.new_token(self.refresh_token,
                                               self.client_id,
                                               self.client_secret)
        except ConnectionError as e:
            log.error('ConnectionError',
                      message=u"Error while getting access token: {}"
                              .format(e),
                      account_id=self.id)
            raise
        except OAuthInvalidGrantError as e:
            log.error('InvalidGrantError',
                      message=u"Error while getting access token: {}"
                              .format(e),
                      account_id=self.id)
            raise
        except OAuthError as e:
            log.error('OAuthError',
                      message=u"Error while getting access token: {}"
                              .format(e),
                      account_id=self.id)
            raise
