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
    """
    Sometimes dns.resolver.Resolver fails to return what we want. See
    http://stackoverflow.com/questions/18898847. In such cases, try using
    dns.query.udp().

    """
    try:
        query = dns.message.make_query(domain, dns.rdatatype.MX)
        answer = dns.query.udp(query, GOOGLE_DNS_IP).answer[0]
        return answer
    except:
        return []


def get_mx_domains(domain):
    """ Retrieve and return the MX records for a domain. """
    mx_records = []
    try:
        mx_records = dns_resolver.query(domain, 'MX')
    except NoNameservers:
        log.error('NoMXservers', domain=domain)
    except NXDOMAIN:
        log.error('No such domain', domain=domain)
    except Timeout:
        log.error('Time out during resolution', domain=domain)
    except NoAnswer:
        log.error('No answer from provider', domain=domain)
        mx_records = _fallback_get_mx_domains(domain)

    return [str(rdata.exchange).lower() for rdata in mx_records]


def mx_match(mx_domains, match_domains):
    """
    Return True if any of the `mx_domains` matches an mx_domain
    in `match_domains`.

    """
    for mx_domain in mx_domains:
        # Depending on how the MX server is configured, domain may
        # refer to a relative name or to an absolute one.
        # FIXME @karim: maybe resolve the server instead.
        if mx_domain[-1] == '.':
            mx_domain = mx_domain[:-1]

        # Match the given domain against any of the mx_server regular
        # expressions we have stored for the given domain. If none of them
        # match, then we cannot confirm this as the given provider
        match_filter = lambda x: re.search(x + '$', mx_domain)
        if any(match_filter(m) for m in match_domains):
            return True

    return False


def provider_from_address(email_address):
    if not EMAIL_REGEX.match(email_address):
        raise InvalidEmailAddressError('Invalid email address')

    domain = email_address.split('@')[1].lower()
    mx_domains = get_mx_domains(domain)
    ns_records = []
    try:
        ns_records = dns_resolver.query(domain, 'NS')
    except NoNameservers:
        log.error('NoNameservers', domain=domain)
    except NXDOMAIN:
        log.error('No such domain', domain=domain)
    except Timeout:
        log.error('Time out during resolution', domain=domain)
    except NoAnswer:
        log.error('No answer from provider', domain=domain)

    for (name, info) in providers.iteritems():
        provider_mx = info.get('mx_servers', [])
        provider_ns = info.get('ns_servers', [])
        provider_domains = info.get('domains', [])

        # If domain is in the list of known domains for a provider,
        # return the provider.
        for d in provider_domains:
            if domain.endswith(d):
                return name

        # If a retrieved mx_domain is in the list of stored MX domains for a
        # provider, return the provider.
        if mx_match(mx_domains, provider_mx):
            return name

        # If a retrieved name server is in the list of stored name servers for
        # a provider, return the provider.
        for rdata in ns_records:
            if str(rdata).lower() in provider_ns:
                return name

    return 'unknown'


# From tornado.httputil
def url_concat(url, args, fragments=None):
    """
    Concatenate url and argument dictionary regardless of whether
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
