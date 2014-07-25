from dns.resolver import Resolver, NoNameservers
from urllib import urlencode
import logging as log
import re


# http://www.regular-expressions.info/email.html
EMAIL_REGEX = re.compile(r'[A-Z0-9._%+-]+@(?:[A-Z0-9-]+\.)+[A-Z]{2,4}',
                         re.IGNORECASE)

# Use Google's Public DNS server (8.8.8.8)
dns_resolver = Resolver()
dns_resolver.nameservers = ['8.8.8.8']

# YAHOO:
# https://en.wikipedia.org/wiki/Yahoo!_Mail#Email_domains
yahoo_mail_domains = [
    'yahoo.com.ar',  # Argentina
    'yahoo.com.au',  # Australia
    'yahoo.at',      # Austria
    'yahoo.be',      # Belgium (French)
    'yahoo.fr',
    'yahoo.be',      # Belgium (Dutch)
    'yahoo.nl',
    'yahoo.com.br',  # Brazil
    'yahoo.ca',      # Canada (English)
    'yahoo.en',
    'yahoo.ca',      # Canada (French)
    'yahoo.fr',
    'yahoo.com.cn',  # China
    'yahoo.cn',
    'yahoo.com.co',  # Colombia
    'yahoo.cz',      # Czech Republic
    'yahoo.dk',      # Denmark
    'yahoo.fi',      # Finland
    'yahoo.fr',      # France
    'yahoo.de',      # Germany
    'yahoo.gr',      # Greece
    'yahoo.com.hk',  # Hong Kong
    'yahoo.hu',      # Hungary
    'yahoo.co.in',   # India
    'yahoo.in',      # Indonesia
    'yahoo.ie',      # Ireland
    'yahoo.co.il',   # Israel
    'yahoo.it',      # Italy
    'yahoo.co.jp',   # Japan
    'yahoo.com.my',  # Malaysia
    'yahoo.com.mx',  # Mexico
    'yahoo.ae',      # Middle East
    'yahoo.nl',      # Netherlands
    'yahoo.co.nz',   # New Zealand
    'yahoo.no',      # Norway
    'yahoo.com.ph',  # Philippines
    'yahoo.pl',      # Poland
    'yahoo.pt',      # Portugal
    'yahoo.ro',      # Romania
    'yahoo.ru',      # Russia
    'yahoo.com.sg',  # Singapore
    'yahoo.co.za',   # South Africa
    'yahoo.es',      # Spain
    'yahoo.se',      # Sweden
    'yahoo.ch',      # Switzerland (French)
    'yahoo.fr',
    'yahoo.ch',      # Switzerland (German)
    'yahoo.de',
    'yahoo.com.tw',  # Taiwan
    'yahoo.co.th',   # Thailand
    'yahoo.com.tr',  # Turkey
    'yahoo.co.uk',   # United Kingdom
    'yahoo.com',     # United States
    'yahoo.com.vn',  # Vietnam

    'ymail.com',     # Newly added!
    'rocketmail.com',
]

# Outlook:
outlook_mail_domains = [
    'hotmail.com',
    'outlook.com',
    'outlook.com.ar',
    'outlook.com.au',
    'outlook.at',
    'outlook.be',
    'outlook.com.br',
    'outlook.cl',
    'outlook.cz',
    'outlook.dk',
    'outlook.fr',
    'outlook.de',
    'outlook.com.gr',
    'outlook.co.il',
    'outlook.in',
    'outlook.co.id',
    'outlook.ie',
    'outlook.it',
    'outlook.hu',
    'outlook.jp',
    'outlook.kr',
    'outlook.lv',
    'outlook.my',
    'outlook.co.nz',
    'outlook.com.pe',
    'outlook.ph',
    'outlook.pt',
    'outlook.sa',
    'outlook.sg',
    'outlook.sk',
    'outlook.es',
    'outlook.co.th',
    'outlook.com.tr',
    'outlook.com.vn',
]

# Aol:
aol_mail_domains = [
    'aol.com',
]

# http://www.ysmallbizstatus.com/status/archives/13024
yahoo_smallbiz_mx_servers = [
    'mx-biz.mail.am0.yahoodns.net',
    'mx1.biz.mail.yahoo.com.',
    'mx5.biz.mail.yahoo.com.',
    'mxvm2.mail.yahoo.com.',
    'mx-van.mail.am0.yahoodns.net'
]

# GOOGLE
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
    'aspmx1.aspmx.l.google.com.',
    'aspmx2.aspmx.l.google.com.',
    'aspmx3.aspmx.l.google.com.',
    'aspmx4.aspmx.l.google.com.',

    # Gmail
    'gmail-smtp-in.l.google.com.',
    'alt1.gmail-smtp-in.l.google.com.',
    'alt2.gmail-smtp-in.l.google.com.',
    'alt3.gmail-smtp-in.l.google.com.',
    'alt4.gmail-smtp-in.l.google.com.'
    ]


class InvalidEmailAddressError(Exception):
    pass


def email_supports_gmail(domain):
    # Must have Gmail or Google Apps MX records
    is_valid = True
    try:
        answers = dns_resolver.query(domain, 'MX')

        # All relay servers must be gmail
        for rdata in answers:
            if not str(rdata.exchange).lower() in gmail_mx_servers:
                is_valid = False

    except NoNameservers:
        log.error("NoNameservers error")
        is_valid = False

    return is_valid


def email_supports_outlook(domain):
    # Must be a Outlook mail domain
    if domain in outlook_mail_domains:
        return True


def email_supports_aol(domain):
    # Must be a AOL mail domain
    if domain in aol_mail_domains:
        return True


def email_supports_yahoo(domain):
    # Must be a Yahoo mail domain
    if domain in yahoo_mail_domains:
        return True

    # Or have a Yahoo small business MX record
    is_valid = True
    try:
        answers = dns_resolver.query(domain, 'MX')

        for rdata in answers:
            if not str(rdata.exchange).lower() in yahoo_smallbiz_mx_servers:
                is_valid = False

    except NoNameservers:
        log.error("NoNameservers error")
        is_valid = False

    return is_valid


def provider_from_address(email_address):
    if not EMAIL_REGEX.match(email_address):
        raise InvalidEmailAddressError('Invalid email address')

    domain = email_address.split('@')[1].lower()

    if email_supports_gmail(domain):
        return 'gmail'

    if email_supports_yahoo(domain):
        return 'yahoo'

    if email_supports_outlook(domain):
        return 'outlook'

    if email_supports_aol(domain):
        return 'aol'

    else:
        return 'eas'


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
