import dns
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
GOOGLE_DNS_IP = '8.8.8.8'
dns_resolver = Resolver()
dns_resolver.nameservers = [GOOGLE_DNS_IP]


class InvalidEmailAddressError(Exception):
    pass


def _fallback_get_mx_domains(domain):
    """Sometimes dns.resolver.Resolver fails to return what we want. See
    http://stackoverflow.com/questions/18898847. In such cases, try using
    dns.query.udp()."""
    try:
        query = dns.message.make_query(domain, dns.rdatatype.MX)
        answer = dns.query.udp(query, GOOGLE_DNS_IP).answer[0]
        return [str(item.exchange).lower() for item in answer]
    except:
        return []


def provider_from_address(email_address):
    if not EMAIL_REGEX.match(email_address):
        raise InvalidEmailAddressError('Invalid email address')

    domain = email_address.split('@')[1].lower()
    mx_domains = []
    try:
        mx_records = dns_resolver.query(domain, 'MX')
        mx_domains = [str(rdata.exchange).lower() for rdata in mx_records]
    except NoNameservers:
        log.error("NoMXservers error", domain=domain)
    except NXDOMAIN:
        log.error("No such domain", domain=domain)
    except Timeout:
        log.error("Timed out while resolving", domain=domain)
    except NoAnswer:
        log.error("Provider didn't answer", domain=domain)
        mx_domains = _fallback_get_mx_domains(domain)

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

        valid = len(mx_domains)
        for mx_domain in mx_domains:
            # Depending on how the MX server is configured, domain may
            # refer to a relative name or to an absolute one.
            # FIXME @karim: maybe resolve the server instead.
            if mx_domain[-1] == '.':
                mx_domain = mx_domain[:-1]

            # match the given domain against any of the mx_server regular
            # expressions we have stored for the given domain. If none of them
            # match, then we cannot confirm this as the given provider
            match_filter = lambda x: re.match(x + '$', mx_domain)
            if len(filter(match_filter, mx_servers)) == 0:
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
