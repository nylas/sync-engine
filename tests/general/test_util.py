# test_util.py --- test various utility functions.
import socket
from inbox.util.url import naked_domain, matching_subdomains


def test_naked_domain():
    assert naked_domain(
        'python.linux.com') == 'python.linux.com'
    assert naked_domain(
        'iplayer.forums.bbc.co.uk') == 'iplayer.forums.bbc.co.uk'
    assert naked_domain(
        'parliament.org.au') == 'parliament.org.au'
    assert naked_domain(
        'prime-minister.parliament.org.au') == 'prime-minister.parliament.org.au'
    assert naked_domain(
        'https://python.linux.com/resume-guido.pdf') == 'python.linux.com'
    assert naked_domain(
        'ftp://linux.com/vmlinuz') == 'linux.com'
    assert naked_domain(
        'ftp://parliament.co.uk/vmlinuz') == 'parliament.co.uk'
    assert naked_domain(
        'ftp://pm.parliament.co.uk/vmlinuz') == 'pm.parliament.co.uk'
    assert naked_domain(
        'https://username:password@python.linux.com/vmlinuz') == 'python.linux.com'


def test_matching_subdomains(monkeypatch):
    def gethostbyname_patch(x):
        return "127.0.0.1"

    monkeypatch.setattr(socket, 'gethostbyname', gethostbyname_patch)

    assert matching_subdomains(None, 'mail.nylas.com') is False

    # Two domains with the same IP but different domains aren't matched.
    assert matching_subdomains('mail.microsoft.com', 'mail.nylas.com') is False
    assert matching_subdomains('test.nylas.co.uk', 'mail.nylas.co.uk') is True
    assert matching_subdomains('test.servers.nylas.com.au', 'mail.nylas.com.au') is True
    assert matching_subdomains('test.servers.nylas.com', 'mail.nylas.com.au') is False
    assert matching_subdomains('test.servers.co.uk', 'evil.co.uk') is False

    addresses = ['127.0.0.1', '192.168.1.11']
    def gethostbyname_patch(x):
        return addresses.pop()

    monkeypatch.setattr(socket, 'gethostbyname', gethostbyname_patch)

    addresses = ['127.0.0.1', '192.168.1.11']
    def gethostbyname_patch(x):
        return addresses.pop()

    # Check that if the domains are the same, we're not doing an
    # IP address resolution.
    assert matching_subdomains('nylas.com', 'nylas.com') is True
