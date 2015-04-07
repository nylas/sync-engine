import pytest
from inbox.providers import providers
from inbox.util.url import provider_from_address
from inbox.util.url import InvalidEmailAddressError
from inbox.auth.base import handler_from_provider
from inbox.auth.generic import GenericAuthHandler
from inbox.auth.gmail import GmailAuthHandler
from inbox.auth.outlook import OutlookAuthHandler
from inbox.basicauth import NotSupportedError


def test_provider_resolution():
    assert provider_from_address('foo@example.com') == 'unknown'
    assert provider_from_address('foo@noresolve.com') == 'unknown'
    assert provider_from_address('foo@gmail.com') == 'gmail'
    assert provider_from_address('foo@yahoo.com') == 'yahoo'
    assert provider_from_address('foo@yahoo.se') == 'yahoo'
    assert provider_from_address('foo@hotmail.com') == 'outlook'
    assert provider_from_address('foo@outlook.com') == 'outlook'
    assert provider_from_address('foo@aol.com') == 'aol'
    assert provider_from_address('foo@love.com') == 'aol'
    assert provider_from_address('foo@games.com') == 'aol'
    assert provider_from_address('foo@exchange.mit.edu') == 'eas'
    assert provider_from_address('foo@fastmail.fm') == 'fastmail'
    assert provider_from_address('foo@fastmail.net') == 'fastmail'
    assert provider_from_address('foo@fastmail.com') == 'fastmail'
    assert provider_from_address('foo@icloud.com') == 'icloud'
    assert provider_from_address('foo@mac.com') == 'icloud'
    assert provider_from_address('foo@gmx.com') == 'gmx'
    assert provider_from_address('foo@gandi.net') == 'gandi'
    assert provider_from_address('foo@debuggers.co') == 'gandi'
    assert provider_from_address('foo@getrhombus.com') == 'eas'
    assert provider_from_address('foo@forumone.com') == 'gmail'
    assert provider_from_address('foo@getbannerman.com') == 'gmail'
    assert provider_from_address('foo@inboxapp.onmicrosoft.com') == 'eas'
    assert provider_from_address('foo@espertech.onmicrosoft.com') == 'eas'
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('notanemail')
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('not@anemail')
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('notanemail.com')

    try:
        # Registering a new provider
        assert provider_from_address('foo@example.com') == 'unknown'
        providers.register_info('example', {
            "type": "generic",
            "imap": ("mail.example.net", 993),
            "smtp": ("smtp.example.net", 587),
            "auth": "password",
            "domains": ["example.com"],
            "mx_servers": ["mx.example.net"]
        })
        assert provider_from_address('foo@example.com') == 'example'

        # Registering some filters
        def aol_filter(info, provider, email):
            info['domains'].append('example.net')

        def wildcard_filter(info, provider, email):
            if provider == 'zimbra':
                info['domains'].append('example.org')

        assert provider_from_address('foo@example.net') == 'unknown'
        assert provider_from_address('foo@example.org') == 'unknown'
        providers.register_info_filter('aol', aol_filter)
        providers.register_info_filter(None, wildcard_filter)
        assert provider_from_address('foo@example.net') == 'aol'
        assert provider_from_address('foo@example.org') == 'zimbra'

        # Modifying provider info based on the email address
        def email_address_filter(info, provider, email):
            if email == 'user2@example.com':
                info['imap'] = ('imap2.example.com', 994)
        orig_imap = tuple(providers['yahoo']['imap'])

        assert (providers.lookup_info('yahoo', 'user2@example.com')['imap'] ==
                orig_imap)
        assert (providers.lookup_info('yahoo', 'user1@example.com')['imap'] ==
                orig_imap)
        providers.register_info_filter(None, email_address_filter)
        assert (providers.lookup_info('yahoo', 'user2@example.com')['imap'] ==
                ('imap2.example.com', 994))
        assert (providers.lookup_info('yahoo', 'user1@example.com')['imap'] ==
                orig_imap)
    finally:
        providers.reset()


def test_auth_handler_dispatch():
    assert isinstance(handler_from_provider('custom'), GenericAuthHandler)
    assert isinstance(handler_from_provider('fastmail'), GenericAuthHandler)
    assert isinstance(handler_from_provider('aol'), GenericAuthHandler)
    assert isinstance(handler_from_provider('yahoo'), GenericAuthHandler)
    assert isinstance(handler_from_provider('gmail'), GmailAuthHandler)
    assert isinstance(handler_from_provider('outlook'), OutlookAuthHandler)

    with pytest.raises(NotSupportedError):
        handler_from_provider('NOTAREALMAILPROVIDER')
