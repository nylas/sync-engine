# TODO perhaps move this to normal auth module...
import sys
import getpass


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


def password_auth(email_address, token, exit, username_prompt=False):
    password_message = 'Password for {0} (hidden): '

    # Certain password flows like EAS could require a username
    username_message = 'Username, if different from email '\
        '(leave blank otherwise): '
    username = None

    if not token:
        if exit:
            print password_message.format(email_address)
            sys.exit(0)
        username = raw_input(username_message).strip() or username if \
            username_prompt else username
        pw = getpass.getpass(password_message.format(email_address))
    else:
        pw = token

    if len(pw) <= 0:
        raise AuthError('Password required.')

    return dict(email=email_address, username=username, password=pw)
