"""
Generic OAuth class that provides abstraction for access and
refresh tokens.
"""
from datetime import datetime, timedelta

from inbox.models.vault import vault
from inbox.oauth import new_token, validate_token
from inbox.basicauth import AuthError

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
            tok, expires = new_token(self.provider_module,
                                     self.refresh_token,
                                     self.client_id,
                                     self.client_secret)

            validate_token(self.provider_module, tok)
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
                    return validate_token(self.provider_module, tok)
                except AuthError:
                    del __volatile_tokens__[self.id]
                    raise

        else:
            tok, expires = new_token(self.provider_module, self.refresh_token)
            valid = validate_token(self.provider_module, tok)
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
