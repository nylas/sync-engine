# TODO(emfree): this is now legitimately just a grab-bag of nebulous
# exceptions.  Rename module and clean up.


class AuthError(Exception):
    pass


class ConnectionError(AuthError):
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


class UserRecoverableConfigError(Exception):
    pass


class GmailSettingError(ValidationError):
    pass


class ImapSupportDisabledError(ValidationError):
    pass


class AccessNotEnabledError(Exception):
    pass
