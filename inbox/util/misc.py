import sys
import pkgutil
import time
import re

from datetime import datetime
from email.utils import parsedate_tz, mktime_tz

from nylas.logging import get_logger
from inbox.providers import providers


class DummyContextManager(object):

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class ProviderSpecificException(Exception):
    pass


def or_none(value, selector):
    if value is None:
        return None
    else:
        return selector(value)


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


def parse_references(references, in_reply_to):
    """
    Parse a References: header and returns an array of MessageIDs.
    The returned array contains the MessageID in In-Reply-To if
    the header is present.

    Parameters
    ----------

    references: string
        the contents of the referfences header

    in_reply_to: string
        the contents of the in-reply-to header

    Returns
    -------
    list of MessageIds (strings) or an empty list.
    """
    replyto = in_reply_to.split()[0] if in_reply_to else in_reply_to

    if not references:
        if replyto:
            return [replyto]
        else:
            return []

    references = references.split()
    if replyto not in references:
        references.append(replyto)

    return references


def dt_to_timestamp(dt):
    return int((dt - datetime(1970, 1, 1)).total_seconds())


def get_internaldate(date, received):
    """ Get the date from the headers. """
    if date is None:
        other, date = received.split(';')

    # All in UTC
    parsed_date = parsedate_tz(date)
    timestamp = mktime_tz(parsed_date)
    dt = datetime.utcfromtimestamp(timestamp)

    return dt


def timed(fn):
    """ A decorator for timing methods. """

    def timed_fn(self, *args, **kwargs):
        start_time = time.time()
        ret = fn(self, *args, **kwargs)

        # TODO some modules like gmail.py don't have self.logger
        try:
            if self.log:
                fn_logger = self.log
        except AttributeError:
            fn_logger = get_logger()
            # out = None
        fn_logger.info('[timer] {0} took {1:.3f} seconds.'.format(
            str(fn), float(time.time() - start_time)))
        return ret
    return timed_fn


# Based on: http://stackoverflow.com/a/8556471
def load_modules(base_name, base_path):
    """
    Imports all modules underneath `base_module` in the module tree.

    Note that if submodules are located in different directory trees, you
    need to use `pkgutil.extend_path` to make all the folders appear in
    the module's `__path__`.

    Returns
    -------
    list
        All the modules in the base module tree.

    """
    modules = []

    for importer, module_name, _ in pkgutil.iter_modules(base_path):
        full_module_name = '{}.{}'.format(base_name, module_name)

        if full_module_name not in sys.modules:
            module = importer.find_module(module_name).load_module(
                full_module_name)
        else:
            module = sys.modules[full_module_name]
        modules.append(module)

    return modules


def register_backends(base_name, base_path):
    """
    Dynamically loads all packages contained within thread
    backends module, including those by other module install paths

    """
    modules = load_modules(base_name, base_path)

    mod_for = {}
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider_name = module.PROVIDER
            if provider_name == 'generic':
                for p_name, p in providers.iteritems():
                    p_type = p.get('type', None)
                    if p_type == 'generic' and p_name not in mod_for:
                        mod_for[p_name] = module
            else:
                mod_for[provider_name] = module

    return mod_for


def cleanup_subject(subject_str):
    """Clean-up a message subject-line, including whitespace.
    For instance, 'Re: Re: Re: Birthday   party' becomes 'Birthday party'"""
    if subject_str is None:
        return ''
    # TODO consider expanding to all
    # http://en.wikipedia.org/wiki/List_of_email_subject_abbreviations
    prefix_regexp = "(?i)^((re|fw|fwd|aw|wg|undeliverable|undelivered):\s*)+"
    subject = re.sub(prefix_regexp, "", subject_str)

    whitespace_regexp = "\s+"
    return re.sub(whitespace_regexp, " ", subject)


# IMAP doesn't support nested folders and instead encodes paths inside folder
# names.
# imap_folder_path converts a "/" delimited path to an IMAP compatible path.
def imap_folder_path(path, separator='.', prefix=''):
    folders = [folder for folder in path.split('/') if folder != '']

    res = None

    if folders:
        res = separator.join(folders)

        if prefix and not res.startswith(prefix):
            # Check that the value we got for the prefix doesn't include
            # the separator too (i.e: `INBOX.` instead of `INBOX`).
            if prefix[-1] != separator:
                res = u"{}{}{}".format(prefix, separator, res)
            else:
                res = u"{}{}".format(prefix, res)

    return res


def strip_prefix(path, prefix):
    if path.startswith(prefix):
        return path[len(prefix):]

    return path


# fs_folder_path converts an IMAP compatible path to a "/" delimited path.
def fs_folder_path(path, separator='.', prefix=''):
    if prefix:
        path = strip_prefix(path, prefix)

    folders = path.split(separator)
    # Remove stray '' which can happen if the folder is prefixed
    # i.e: INBOX.Taxes.Accounting -> .Taxes.Accounting -> ['', 'Taxes', 'Accounting']
    if folders[0] == '':
        folders.pop(0)

    return '/'.join(folders)
