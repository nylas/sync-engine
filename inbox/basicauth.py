# TODO(emfree): this is now legitimately just a grab-bag of nebulous
# exceptions.  Rename module and clean up.


class AuthError(Exception):
    pass


class ConnectionError(AuthError):
    pass


class TransientConnectionError(ConnectionError):
    """A potentially transient error. Handler should retry
    the call, at least once."""
    pass


class ValidationError(AuthError):
    pass


class NotSupportedError(AuthError):
    pass


class PermissionsError(Exception):
    pass


class OAuthError(ValidationError):
    pass


class ConfigError(Exception):
    pass


class UserRecoverableConfigError(ConfigError):
    pass


class AccessNotEnabledError(Exception):
    pass
