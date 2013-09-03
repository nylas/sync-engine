import itertools
import string
from dns.resolver import query as dns_query
from urllib import urlencode
import requests
from tornado import escape
import logging as log
import zerorpc
from gevent import Greenlet
from time import sleep


def chunk(iterable, size):
    """ Yield chunks of an iterable.

    If len(iterable) is not evenly divisible by size, the last chunk will be
    shorter than size.
    """
    it = iter(iterable)
    while True:
        group = tuple(itertools.islice(it, None, size))
        if not group:
            break
        yield group

def human_readable_filesize(size_bytes, suffixes=None):
    """
    format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
    Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
    e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
    """
    if size_bytes == 1:
        # because I really hate unnecessary plurals
        return "1 byte"

    if not suffixes:
        suffixes = [('bytes',0),('KB',0),('MB',1),('GB',2),('TB',2), ('PB',2)]

    num = float(size_bytes)
    for suffix, precision in suffixes:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s %s" % (formatted_size, suffix)

def or_none(value, selector):
    if value is None:
        return None
    else:
        return selector(value)

def partition(pred, iterable):
    'Use a predicate to partition entries into false entries and true entries'
    # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
    t1, t2 = itertools.tee(iterable)
    return list(itertools.ifilterfalse(pred, t1)), filter(pred, t2)

def safe_filename(filename):
    """ Strip potentially bad characters from a filename so it is safe to
        write to disk.
    """
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    return ''.join(c for c in filename if c in valid_chars)

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


def make_zerorpc(cls, location):
    def m():
        """ Exposes the given class as a ZeroRPC server on the given address+port """
        s = zerorpc.Server(cls())
        s.bind(location)
        log.info("ZeroRPC: Starting %s at %s" % (cls.__name__, location))
        s.run()
    Greenlet.spawn(m)


def print_dots():
    """This Greenlet prints dots to the console which is useful for making
    sure that other greenlets are properly not blocking."""
    def m():
        while True:
            sys.stdout.write("."),
            sys.stdout.flush()
            sleep(.02)
    Greenlet.spawn(m)


