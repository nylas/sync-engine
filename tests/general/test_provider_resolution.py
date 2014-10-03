import pytest
from inbox.providers import providers
from inbox.util.url import provider_from_address
from inbox.util.url import InvalidEmailAddressError


def test_provider_resolution():
    assert provider_from_address('foo@example.com') == 'unknown'
    assert provider_from_address('foo@noresolve.com') == 'unknown'
    assert provider_from_address('foo@gmail.com') == 'gmail'
    assert provider_from_address('foo@inboxapp.com') == 'gmail'
    assert provider_from_address('foo@yahoo.com') == 'yahoo'
    assert provider_from_address('foo@yahoo.se') == 'yahoo'
    assert provider_from_address('foo@hotmail.com') == 'outlook'
    assert provider_from_address('foo@outlook.com') == 'outlook'
    assert provider_from_address('foo@aol.com') == 'aol'
    assert provider_from_address('foo@love.com') == 'aol'
    assert provider_from_address('foo@games.com') == 'aol'
    assert provider_from_address('foo@inboxapp.com') == 'gmail'
    assert provider_from_address('foo@exchange.mit.edu') == 'eas'
    assert provider_from_address('foo@fastmail.fm') == 'fastmail'
    assert provider_from_address('foo@fastmail.net') == 'fastmail'
    assert provider_from_address('foo@fastmail.com') == 'fastmail'
    assert provider_from_address('foo@icloud.com') == 'icloud'
    assert provider_from_address('foo@mac.com') == 'icloud'
    assert provider_from_address('foo@gmx.com') == 'gmx'
    assert provider_from_address('foo@gandi.net') == 'gandi'
    assert provider_from_address('foo@debuggers.co') == 'gandi'
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('notanemail')
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('not@anemail')
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('notanemail.com')

    # Register a new provider
    try:
        providers.register_info('example', {
            "type": "generic",
            "imap": ("mail.example.net", 993),
            "smtp": ("smtp.example.net", 587),
            "auth": "password",
            "domains": ["example.com"],
            "mx_servers": ["mx.example.net"]
        })
        assert provider_from_address('foo@example.com') == 'example'
    finally:
        providers.reset()

    # Register a filter
    try:
        def my_filter(name, info):
            info['domains'].append('example.net')
        assert provider_from_address('foo@example.net') == 'unknown'
        providers.register_info_filter('aol', my_filter)
        assert provider_from_address('foo@example.net') == 'aol'
    finally:
        providers.reset()
