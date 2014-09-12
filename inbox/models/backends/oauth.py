"""
Generic OAuth class that provides abstraction for access and
refresh tokens.
"""
from datetime import datetime, timedelta

from inbox.models.vault import vault
from inbox.oauth import new_token, validate_token
from inbox.basicauth import AuthError
from inbox.basicauth import ConnectionError
from inbox.oauth import (OAuthInvalidGrantError,
                         OAuthValidationError,
                         OAuthError)

from inbox.log import get_logger
log = get_logger()

__volatile_tokens__ = {}


class OAuthAccount(object):
    @property
    def provider_module(self):
        from inbox.auth import handler_from_provider
        return handler_from_provider(self.provider)

    @property
    def refresh_token(self):
        return vault.get(self.refresh_token_id)

    @refresh_token.setter
    def refresh_token(self, value):
        self.refresh_token_id = vault.put(value)

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
            self.access_token()
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
            log.error("Error setting expired access_token for {}"
                      .format(self.id))
            return

        __volatile_tokens__[self.id] = tok, expires

    def _validate_token(self, tok):
        try:
            return validate_token(self.provider_module, tok)
        except ConnectionError as e:
            log.error('ConnectionError',
                      message="Error while validating access token: " + str(e),
                      account_id=self.id)
            raise
        except OAuthValidationError as e:
            log.error('ValidationError',
                      message="Error while validating access token: " + str(e),
                      account_id=self.id)
            raise

    def _new_token(self, tok):
        try:
            return new_token(self.provider_module,
                             self.refresh_token,
                             self.client_id,
                             self.client_secret)
        except ConnectionError as e:
            log.error('ConnectionError',
                      message="Error while getting access token: " + str(e),
                      account_id=self.id)
        except OAuthInvalidGrantError as e:
            log.error('InvalidGrantError',
                      message="Error while getting access token: " + str(e),
                      account_id=self.id)
        except OAuthError as e:
            log.error('OAuthError',
                      message="Error while getting access token: " + str(e),
                      account_id=self.id)
