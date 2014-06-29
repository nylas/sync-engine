# TODO perhaps move this to normal auth module...
import getpass

AUTH_TYPES = {'gmail': 'oauth', 'yahoo': 'password', 'eas': 'password'}

# Certain password auths flows (like EAS) provide their own message
default_message = 'Password for {0} (hidden): '


class AuthError(Exception):
    pass


def password_auth(email_address, message=default_message):
    pw = getpass.getpass(message.format(email_address))

    if len(pw) <= 0:
        raise AuthError('Password required.')

    return dict(email=email_address, password=pw)
