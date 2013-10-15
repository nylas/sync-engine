from dns.resolver import query as dns_query
from urllib import urlencode
import requests

import logging as log

def validate_email(address_text):

    args = {
        "address": address_text
        }

    MAILGUN_API_PUBLIC_KEY = "pubkey-8nre-3dq2qn8-jjopmq9wiwu4pk480p2"
    MAILGUN_VALIDATE_API_URL = "https://api.mailgun.net/v2/address/validate?" + urlencode(args)

    try:
        response = requests.get(MAILGUN_VALIDATE_API_URL,
                    auth=('api', MAILGUN_API_PUBLIC_KEY))
    except Exception, e:
        log.error(e)
        return None  # TODO better error handling here

    body = response.json()

    is_valid = body['is_valid']
    if is_valid:
        # Must have Gmail or Google Apps MX records
        domain = body['parts']['domain']
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

    return dict(
        valid_for_inbox = is_valid,
        did_you_mean = body['did_you_mean'],
        valid_address = body['address']
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
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
