from dns.resolver import query as dns_query, NoNameservers
from urllib import urlencode
import logging as log
import re

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

def validate_email(address_text):

    is_valid = True

    if not EMAIL_REGEX.match(address_text):
        is_valid = False
    else:
        # Must have Gmail or Google Apps MX records
        domain = address_text.split('@')[1]
        try:
            answers = dns_query(domain, 'MX')
            gmail_mx_servers = [
                        # Google apps for your domain
                        'aspmx.l.google.com.',
                        'aspmx2.googlemail.com.',
                        'aspmx3.googlemail.com.',
                        'aspmx4.googlemail.com.',
                        'aspmx5.googlemail.com.',
                        'alt1.aspmx.l.google.com.',
                        'alt2.aspmx.l.google.com.',
                        'alt3.aspmx.l.google.com.',
                        'alt4.aspmx.l.google.com.',

                        # Gmail
                        'gmail-smtp-in.l.google.com.',
                        'alt1.gmail-smtp-in.l.google.com.',
                        'alt2.gmail-smtp-in.l.google.com.',
                        'alt3.gmail-smtp-in.l.google.com.',
                        'alt4.gmail-smtp-in.l.google.com.'
                         ]
            # All relay servers must be gmail
            for rdata in answers:
                if not str(rdata.exchange).lower() in gmail_mx_servers:
                    is_valid = False
                    log.error("Non-Google MX record: %s" % str(rdata.exchange))

        except NoNameservers:
            is_valid = False


        return dict(
            valid_for_inbox = is_valid,
            valid_address = address_text
        )


# From tornado.httputil
def url_concat(url, args):
    """Concatenate url and argument dictionary regardless of whether
    url has existing query parameters.

    >>> url_concat("http://example.com/foo?a=b", dict(c="d"))
    'http://example.com/foo?a=b&c=d'
    """
    if not args:
        return url
    if url[-1] not in ('?', '&'):
        url += '&' if ('?' in url) else '?'
    return url + urlencode(args)
