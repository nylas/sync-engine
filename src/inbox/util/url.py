from dns.resolver import query as dns_query, NoNameservers
from urllib import urlencode
import logging as log
import re

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

# https://en.wikipedia.org/wiki/Yahoo!_Mail#Email_domains
# YAHOO:
yahoo_mail_domains = [
    'yahoo.com.ar', # Argentina
    'yahoo.com.au', # Australia
    'yahoo.at',     # Austria
    'yahoo.be',     # Belgium (French)
    'yahoo.fr',
    'yahoo.be',     # Belgium (Dutch)
    'yahoo.nl',
    'yahoo.com.br', # Brazil
    'yahoo.ca',     # Canada (English)
    'yahoo.en',
    'yahoo.ca',     # Canada (French)
    'yahoo.fr',
    'yahoo.com.cn', # China
    'yahoo.cn',
    'yahoo.com.co', # Colombia
    'yahoo.cz',     # Czech Republic
    'yahoo.dk',     # Denmark
    'yahoo.fi',     # Finland
    'yahoo.fr',     # France
    'yahoo.de',     # Germany
    'yahoo.gr',     # Greece
    'yahoo.com.hk', # Hong Kong
    'yahoo.hu',     # Hungary
    'yahoo.co.in',  # India
    'yahoo.in',     # Indonesia
    'yahoo.ie',     # Ireland
    'yahoo.co.il',  # Israel
    'yahoo.it',     # Italy
    'yahoo.co.jp',  # Japan
    'yahoo.com.my', # Malaysia
    'yahoo.com.mx', # Mexico
    'yahoo.ae',     # Middle East
    'yahoo.nl',     # Netherlands
    'yahoo.co.nz',  # New Zealand
    'yahoo.no',     # Norway
    'yahoo.com.ph', # Philippines
    'yahoo.pl',     # Poland
    'yahoo.pt',     # Portugal
    'yahoo.ro',     # Romania
    'yahoo.ru',     # Russia
    'yahoo.com.sg', # Singapore
    'yahoo.co.za',  # South Africa
    'yahoo.es',     # Spain
    'yahoo.se',     # Sweden
    'yahoo.ch',     # Switzerland (French)
    'yahoo.fr',
    'yahoo.ch',     # Switzerland (German)
    'yahoo.de',
    'yahoo.com.tw', # Taiwan
    'yahoo.co.th',  # Thailand
    'yahoo.com.tr', # Turkey
    'yahoo.co.uk',  # United Kingdom
    'yahoo.com',    # United States
    'yahoo.com.vn', # Vietnam

    'ymail.com',    # Newly added!
    'rocketmail.com',
]

# GMAIL:
def email_supports_gmail(address_text):

    # TODO: FIX THIS, d'uh!
    #return True

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

    return is_valid

def provider_from_address(email_address):
    if email_supports_gmail(email_address):
        return 'Gmail'

    domain = email_address.split('@')[-1].lower()

    if domain in yahoo_mail_domains:
        return 'Yahoo'

    return 'Unknown'

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
