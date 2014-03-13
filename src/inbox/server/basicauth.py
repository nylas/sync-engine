# TODO perhaps move this to normal auth module...
import getpass

AUTH_TYPES = {'Gmail': 'OAuth', 'Yahoo': 'Password', 'EAS': 'Password'}


class AuthError(Exception):
    pass


def password_auth(email_address):
    pw = getpass.getpass('Password for %s (hidden): ' % email_address)

    if len(pw) <= 0:
        raise AuthError('Password required.')

    return dict(email=email_address, password=pw)
