import sys
import pkgutil
import time

from datetime import datetime
from email.utils import parsedate_tz, mktime_tz

from inbox.log import get_logger
from inbox.providers import providers


def or_none(value, selector):
    if value is None:
        return None
    else:
        return selector(value)


def strip_plaintext_quote(text):
    """
    Strip out quoted text with no inline responses.

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
        return '\n'.join(lines[:quote_start - 1])
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
    return int(time.mktime(dt.timetuple()))


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


def merge_attr(base, remote, dest, attr_name):
    """Merge changes from remote into dest if there are no conflicting
    updates to remote and dest relative to base.

    Parameters
    ----------
    base, remote, dest: target object type

    Raises
    ------
    MergeError
        If there is a conflict.
    """

    try:
        base_attr = getattr(base, attr_name) if base else None
        remote_attr = getattr(remote, attr_name) if remote else None
        dest_attr = getattr(dest, attr_name) if dest else None
    except AttributeError:
        # We may have received dicts instead of objects. In this case, use get()
        base_attr = base.get(attr_name) if base else None
        remote_attr = remote.get(attr_name) if remote else None
        dest_attr = dest.get(attr_name) if dest else None

    if (base_attr != dest_attr != remote_attr != base_attr):
        raise MergeError('Conflicting updates to {0}, {1} from {2} on: {3}'
                         .format(remote, dest, base, attr_name))

    if base_attr != remote_attr:
        try:
            setattr(dest, attr_name, remote_attr)
        except AttributeError:
            # Once again, we may have received dicts instead of objects
            dest[attr_name] = remote_attr


class MergeError(Exception):
    pass


class ProviderSpecificException(Exception):
    pass
