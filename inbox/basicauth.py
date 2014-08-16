# TODO perhaps move this to normal auth module...
import sys
import getpass

# Certain password auths flows (like EAS) provide their own message
default_message = 'Password for {0} (hidden): '


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


def password_auth(email_address, token, exit, message=default_message):
    if not token:
        if exit:
            print message.format(email_address)
            sys.exit(0)
        pw = getpass.getpass(message.format(email_address))
    else:
        pw = token

    if len(pw) <= 0:
        raise AuthError('Password required.')

    return dict(email=email_address, password=pw)
