from dns.resolver import Resolver
from dns.resolver import NoNameservers, NXDOMAIN, Timeout, NoAnswer
from urllib import urlencode
from inbox.log import get_logger
import re
log = get_logger('inbox.util.url')

from inbox.providers import providers

# http://www.regular-expressions.info/email.html
EMAIL_REGEX = re.compile(r'[A-Z0-9._%+-]+@(?:[A-Z0-9-]+\.)+[A-Z]{2,4}',
                         re.IGNORECASE)

# Use Google's Public DNS server (8.8.8.8)
dns_resolver = Resolver()
dns_resolver.nameservers = ['8.8.8.8']


class InvalidEmailAddressError(Exception):
    pass


def provider_from_address(email_address):
    if not EMAIL_REGEX.match(email_address):
        raise InvalidEmailAddressError('Invalid email address')

    domain = email_address.split('@')[1].lower()

    mx_records = []
    try:
        mx_records = dns_resolver.query(domain, 'MX')
    except NoNameservers:
        log.error("NoMXservers error", domain=domain)
    except NXDOMAIN:
        log.error("No such domain", domain=domain)
    except Timeout:
        log.error("Timed out while resolving", domain=domain)
    except NoAnswer:
        log.error("Provider didn't answer", domain=domain)

    ns_records = []
    try:
        ns_records = dns_resolver.query(domain, 'NS')
    except NoNameservers:
        log.error("NoNameservers error", domain=domain)
    except NXDOMAIN:
        log.error("No such domain", domain=domain)
    except Timeout:
        log.error("Timed out while resolving", domain=domain)
    except NoAnswer:
        log.error("Provider didn't answer", domain=domain)

    for (p_name, p) in providers.iteritems():
        mx_servers = p.get('mx_servers', [])
        ns_servers = p.get('ns_servers', [])
        domains = p.get('domains', [])
        if domain in domains:
            return p_name

        valid = len(mx_records)
        for rdata in mx_records:
            if str(rdata.exchange).lower() not in mx_servers:
                valid = False
                break

        if valid:
            return p_name

        valid = len(ns_records)
        for rdata in ns_records:
            if str(rdata).lower() not in ns_servers:
                valid = False
                break

        if valid:
            return p_name

    return 'unknown'


# From tornado.httputil
def url_concat(url, args, fragments=None):
    """Concatenate url and argument dictionary regardless of whether
    url has existing query parameters.

    >>> url_concat("http://example.com/foo?a=b", dict(c="d"))
    'http://example.com/foo?a=b&c=d'
    """

    if not args and not fragments:
        return url

    # Strip off hashes
    while url[-1] == '#':
        url = url[:-1]

    fragment_tail = ''
    if fragments:
        fragment_tail = '#' + urlencode(fragments)

    args_tail = ''
    if args:
        if url[-1] not in ('?', '&'):
            args_tail += '&' if ('?' in url) else '?'
        args_tail += urlencode(args)

    return url + args_tail + fragment_tail
