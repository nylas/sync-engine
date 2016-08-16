import json
import os
import pytest
from inbox.util.url import provider_from_address
from inbox.util.url import InvalidEmailAddressError
from inbox.auth.base import handler_from_provider
from inbox.auth.generic import GenericAuthHandler
from inbox.auth.gmail import GmailAuthHandler
from inbox.basicauth import NotSupportedError
from inbox.util.testutils import MockDNSResolver


def test_provider_resolution():
    dns_resolver = MockDNSResolver('dns.json')
    test_cases = [
        ('foo@example.com', 'unknown'),
        ('foo@noresolve.com', 'unknown'),
        ('foo@gmail.com', 'gmail'),
        ('foo@postini.com', 'gmail'),
        ('foo@yahoo.com', 'yahoo'),
        ('foo@yahoo.se', 'yahoo'),
        ('foo@hotmail.com', 'outlook'),
        ('foo@outlook.com', 'outlook'),
        ('foo@aol.com', 'aol'),
        ('foo@love.com', 'aol'),
        ('foo@games.com', 'aol'),
        ('foo@exchange.mit.edu', 'eas'),
        ('foo@fastmail.fm', 'fastmail'),
        ('foo@fastmail.net', 'fastmail'),
        ('foo@fastmail.com', 'fastmail'),
        ('foo@hover.com', 'hover'),
        ('foo@yahoo.com', 'yahoo'),
        ('foo@yandex.com', 'yandex'),
        ('foo@mrmail.com', 'zimbra'),
        ('foo@icloud.com', 'icloud'),
        ('foo@mac.com', 'icloud'),
        ('foo@gmx.com', 'gmx'),
        ('foo@gandi.net', 'gandi'),
        ('foo@debuggers.co', 'gandi'),
        ('foo@forumone.com', 'gmail'),
        ('foo@getbannerman.com', 'gmail'),
        ('foo@inboxapp.onmicrosoft.com', 'eas'),
        ('foo@espertech.onmicrosoft.com', 'eas'),
        ('foo@doesnotexist.nilas.com', 'unknown'),
        ('foo@autobizbrokers.com', 'bluehost'),
    ]
    for email, expected_provider in test_cases:
        assert provider_from_address(email, lambda: dns_resolver) == expected_provider

    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('notanemail', lambda: dns_resolver)
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('not@anemail', lambda: dns_resolver)
    with pytest.raises(InvalidEmailAddressError):
        provider_from_address('notanemail.com', lambda: dns_resolver)


def test_auth_handler_dispatch():
    assert isinstance(handler_from_provider('custom'), GenericAuthHandler)
    assert isinstance(handler_from_provider('fastmail'), GenericAuthHandler)
    assert isinstance(handler_from_provider('aol'), GenericAuthHandler)
    assert isinstance(handler_from_provider('yahoo'), GenericAuthHandler)
    assert isinstance(handler_from_provider('gmail'), GmailAuthHandler)

    with pytest.raises(NotSupportedError):
        handler_from_provider('NOTAREALMAILPROVIDER')
