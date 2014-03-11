import os, sys, pkgutil, time
from inbox.server.log import get_logger


def or_none(value, selector):
    if value is None:
        return None
    else:
        return selector(value)


def strip_plaintext_quote(text):
    """ Strip out quoted text with no inline responses.

    TODO: Make sure that the line before the quote looks vaguely like
    a quote header. May be hard to do in an internationalized manner?
    """
    found_quote = False
    lines = text.strip().splitlines()
    quote_start = None
    for i, line in enumerate(lines):
        if line.startswith('>'):
            found_quote = True
            if quote_start is None:
                quote_start = i
        else:
            found_quote = False
    if found_quote:
        return '\n'.join(lines[:quote_start-1])
    else:
        return text


def parse_ml_headers(headers):
    """
    Parse the mailing list headers described in RFC 4021,
    these headers are optional (RFC 2369).
    """
    attrs = {}
    attrs['List-Archive'] = headers.get('List-Archive')
    attrs['List-Help'] = headers.get('List-Help')
    attrs['List-Id'] = headers.get('List-Id')
    attrs['List-Owner'] = headers.get('List-Owner')
    attrs['List-Post'] = headers.get('List-Post')
    attrs['List-Subscribe'] = headers.get('List-Subscribe')
    attrs['List-Unsubscribe'] = headers.get('List-Unsubscribe')

    return attrs


def timed(fn):
    """ A decorator for timing methods. """
    def timed_fn(self, *args, **kwargs):
        start_time = time.time()
        ret = fn(self, *args, **kwargs)

        # TOFIX the gmail.py module doesn't have self.lgoger
        try:
            if self.log:
                fn_logger = self.log
        except AttributeError:
            fn_logger = get_logger()
            # out = None
        fn_logger.info("[timer] {0} took {1:.3f} seconds.".format(str(fn), float(time.time() - start_time)))
        return ret
    return timed_fn


# From: http://stackoverflow.com/a/8556471
def load_modules(dirname):
    modules = []

    for importer, package_name, _ in pkgutil.iter_modules([dirname]):
        full_package_name = os.path.join(dirname, package_name)

        if full_package_name not in sys.modules:
            module = importer.find_module(package_name).load_module(
                full_package_name)
            modules.append(module)

    return modules
