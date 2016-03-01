import pytest
from inbox.util.url import provider_from_address
from inbox.util.url import InvalidEmailAddressError
from inbox.auth.base import handler_from_provider
from inbox.auth.generic import GenericAuthHandler
from inbox.auth.gmail import GmailAuthHandler
from inbox.basicauth import NotSupportedError


def test_provider_resolution():
    assert provider_from_address('foo@example.com') == 'unknown'
    assert provider_from_address('foo@noresolve.com') == 'unknown'
    assert provider_from_address('foo@gmail.com') == 'gmail'
    assert provider_from_address('foo@postini.com') == 'gmail'
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
    assert provider_from_address('foo@hover.com') == 'hover'
    assert provider_from_address('foo@yahoo.com') == 'yahoo'
    assert provider_from_address('foo@yandex.com') == 'yandex'
    assert provider_from_address('foo@mrmail.com') == 'zimbra'
    assert provider_from_address('foo@icloud.com') == 'icloud'
    assert provider_from_address('foo@mac.com') == 'icloud'
    assert provider_from_address('foo@gmx.com') == 'gmx'
    assert provider_from_address('foo@gandi.net') == 'gandi'
    assert provider_from_address('foo@debuggers.co') == 'gandi'
    assert provider_from_address('foo@forumone.com') == 'gmail'
    assert provider_from_address('foo@getbannerman.com') == 'gmail'
    assert provider_from_address('foo@inboxapp.onmicrosoft.com') == 'eas'
    assert provider_from_address('foo@espertech.onmicrosoft.com') == 'eas'
    assert provider_from_address('foo@doesnotexist.nilas.com') == 'unknown'
    assert provider_from_address('foo@autobizbrokers.com') == 'bluehost'

    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('notanemail')
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('not@anemail')
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('notanemail.com')


def test_auth_handler_dispatch():
    assert isinstance(handler_from_provider('custom'), GenericAuthHandler)
    assert isinstance(handler_from_provider('fastmail'), GenericAuthHandler)
    assert isinstance(handler_from_provider('aol'), GenericAuthHandler)
    assert isinstance(handler_from_provider('yahoo'), GenericAuthHandler)
    assert isinstance(handler_from_provider('gmail'), GmailAuthHandler)

    with pytest.raises(NotSupportedError):
        handler_from_provider('NOTAREALMAILPROVIDER')
