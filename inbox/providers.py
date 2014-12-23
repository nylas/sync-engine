from __future__ import absolute_import, division, print_function

from inbox.config import config

import copy
import functools
import pkg_resources

from collections import Mapping, MutableMapping, defaultdict
from inbox.basicauth import NotSupportedError

__all__ = ['provider_info', 'providers', 'PluginInterface', 'ProvidersDict']


def provider_info(provider_name, email_address=None):
    """Like providers[provider_name] except raises
    inbox.basicauth.NotSupportedError instead of KeyError when the provider is
    not found.

    Parameters
    ----------
    email_address : str or None
        Allows further customization of the return value on a per-account
        basis.
    """
    if provider_name not in providers:
        raise NotSupportedError("Provider: {} not supported.".format(
            provider_name))

    return providers.lookup_info(provider_name, email_address)


class ProvidersDict(MutableMapping):
    """ProvidersDict dictionary with support for lazy-loading plugins.

    Example setup.py boilerplate:

        entry_points={
            'inbox.providers': [
                'register = your.plugin.module:register',
            ],
        },


    Example plugin registration function (`providers` is a PluginInterface
    object):

        # your/plugin/module.py

        def register(providers):
            providers.register_info('example', {
                "type": "generic",
                "imap": ("mail.example.net", 993),
                "smtp": ("smtp.example.net", 587),
                "auth": "password",
                "domains": ["example.com"],
                "mx_servers": ["mx.example.net"]
            })
    """

    def __init__(self):
        self._d = {}
        self._filters = defaultdict(list)
        self._loaded = False

    def reset(self):
        self._d.clear()
        self._filters.clear()
        self._loaded = False

    def __getitem__(self, name):
        return self.lookup_info(name)

    def lookup_info(self, provider_name, email_address=None):
        self.load()
        name = provider_name
        info = self._d[name]

        filters = []
        filters += self._filters[name] if name in self._filters else []
        filters += self._filters[None] if None in self._filters else []
        if filters:
            info = copy.deepcopy(info)
            for func in filters:
                ret = func(info=info, provider=name, email=email_address)
                if ret is not None:
                    info = ret

        return info

    def __setitem__(self, name, info):
        self.load()
        self._d[name] = info

    def __delitem__(self, name):
        self.load()
        del self._d[name]

    def __iter__(self):
        self.load()
        return iter(self._d)

    def __len__(self):
        self.load()
        return len(self._d)

    def load(self):
        if self._loaded:
            return

        self.reset()

        providers = PluginInterface(self)
        group = 'inbox.providers'
        name = 'register'
        for entry_point in pkg_resources.iter_entry_points(group, name):
            register_func = entry_point.load()
            register_func(providers)

        # Load the defaults last so that they can be replaced by plugins.
        self._d.update({k: v for k, v in get_default_providers().items()
                        if k not in self._d})

        # XXX temporary
        if config.get('GMAIL_SMTP_PROXY'):
            self._d['gmail']['smtp'] = config.get('GMAIL_SMTP_PROXY')

        self._loaded = True

    def register_info(self, name, info):
        """Register information for a new provider.

        Parameters
        ----------
        name : str
            The programmatic name of the provider as it's referenced in the
            database.

        info : dict or callable
            Information about this provider.  The `info` dictionary may
            contain the items such as:

            type : str
                Account type, usually `'generic'`.

            imap : (host, port)
                Address of the IMAPS server.

            smtp : (host, port)
                Address of the SMTP server.

            auth : str
                Type of authentication, usually `'password'` or `'oauth2'`.

            domains : list of str
                List of this provider's domains.

            mx_servers : list of str
                List of MX servers for email addresses on this domain.  Useful
                for email providers that allow users to use their own domains.

        Example
        -------

            providers.register_info('aol', {
                "imap": ("imap.aol.com", 993),
                "smtp": ("smtp.aol.com", 587),
                "auth": "password",
                "domains": ["aol.com"],
                "mx_servers": ["mailin-01.mx.aol.com", "mailin-02.mx.aol.com",
                               "mailin-03.mx.aol.com", "mailin-04.mx.aol.com"],
            })
        """

        if not isinstance(name, str):
            raise TypeError('name must by a str')
        if not isinstance(info, Mapping):
            raise TypeError('info must be a dict-like object')
        if name in self._d:
            raise ValueError('Conflict: {0!r} already loaded'.format(name))
        self._d[name] = info

    def register_info_filter(self, name, func):
        """Register a filter for the return value of __getitem__.

        Parameters
        ----------
        name : str or None
            The programmatic name of the provider as it's referenced in the
            database.

            If `name` is None, then the function will be applied to all
            providers.

        func : callable
            A function that accepts the keyword arguments `info`, `provider`,
            and `email` and returns a dictionary of provider info.

            `info` is a copy of the provider dictionary, so it should be safe
            to modify.

        Experimental
        ------------

        This function is experimental; It may change or be removed in a future
        release without warning.
        """
        if not callable(func):
            raise TypeError('func should be callable')
        self._filters[name].append(func)


class PluginInterface(object):
    """Wrapper around ProvidersDict class used during plugin load."""

    def __init__(self, providers):
        self.__providers = providers

    @functools.wraps(ProvidersDict.register_info)
    def register_info(self, name, info):
        return self.__providers.register_info(name, info)

    @functools.wraps(ProvidersDict.register_info_filter)
    def register_info_filter(self, name, func):
        return self.__providers.register_info_filter(name, func)


get_default_providers = lambda: {
    "aol": {
        "type": "generic",
        "imap": ("imap.aol.com", 993),
        "smtp": ("smtp.aol.com", 587),
        "auth": "password",
        "domains": ["aol.com"],
        "mx_servers": ["mailin-01.mx.aol.com", "mailin-02.mx.aol.com",
                       "mailin-03.mx.aol.com", "mailin-04.mx.aol.com"]
    },
    "eas": {
        "auth": "password",
        "domains": [
            "onmicrosoft.com",
            "exchange.mit.edu",
        ],
        "mx_servers": ["protection.outlook.com"]
    },
    "fastmail": {
        "type": "generic",
        "condstore": True,
        "imap": ("mail.messagingengine.com", 993),
        "smtp": ("mail.messagingengine.com", 587),
        "auth": "password",
        "folder_map": {"INBOX.Archive": "archive",
                       "INBOX.Drafts": "drafts", "INBOX.Junk Mail": "spam",
                       "INBOX.Sent Items": "sent", "INBOX.Trash": "trash"},
        "domains": ["fastmail.fm"],
        "mx_servers": ["in1-smtp.messagingengine.com",
                       "in2-smtp.messagingengine.com"],
        "ns_servers": ["ns1.messagingengine.com.",
                       "ns2.messagingengine.com."]
    },
    "gandi": {
        "type": "generic",
        "condstore": True,
        "imap": ("mail.gandi.net", 993),
        "smtp": ("mail.gandi.net", 587),
        "auth": "password",
        "domains": ["debuggers.co"],
        "mx_servers": ["spool.mail.gandi.net", "fb.mail.gandi.net",
                       "mail4.gandi.net", "mail5.gandi.net"],
    },
    "gmail": {
        "imap": ("imap.gmail.com", 993),
        "smtp": ("smtp.gmail.com", 587),
        "auth": "oauth2",
        "events": True,
        "contacts": True,
        "mx_servers": ["aspmx.l.google.com",
                       "aspmx2.googlemail.com",
                       "aspmx3.googlemail.com",
                       "aspmx4.googlemail.com",
                       "aspmx5.googlemail.com",
                       "alt1.aspmx.l.google.com",
                       "alt2.aspmx.l.google.com",
                       "alt3.aspmx.l.google.com",
                       "alt4.aspmx.l.google.com",
                       "aspmx1.aspmx.l.google.com",
                       "aspmx2.aspmx.l.google.com",
                       "aspmx3.aspmx.l.google.com",
                       "aspmx4.aspmx.l.google.com",
                       "gmail-smtp-in.l.google.com",
                       "alt1.gmail-smtp-in.l.google.com",
                       "alt2.gmail-smtp-in.l.google.com",
                       "alt3.gmail-smtp-in.l.google.com",
                       "alt4.gmail-smtp-in.l.google.com",
                       # Postini
                       ".*.psmtp.com"],
    },
    "gmx": {
        "type": "generic",
        "imap": ("imap.gmx.com", 993),
        "smtp": ("smtp.gmx.com", 587),
        "auth": "password",
        "domains": ["gmx.us", "gmx.com"],
    },
    "hover": {
        "type": "generic",
        "imap": ("mail.hover.com", 993),
        "smtp": ("mail.hover.com", 587),
        "auth": "password",
        "mx_servers": ["mx.hover.com.cust.hostedemail.com"],
    },
    "icloud": {
        "type": "generic",
        "imap": ("imap.mail.me.com", 993),
        "smtp": ("smtp.mail.me.com", 587),
        "auth": "password",
        "events": False,
        "folder_map": {"Sent Messages": "sent",
                       "Deleted Messages": "trash"},
        "domains": ["icloud.com"],
        "mx_servers": ["mx1.mail.icloud.com", "mx2.mail.icloud.com",
                       "mx3.mail.icloud.com", "mx4.mail.icloud.com",
                       "mx5.mail.icloud.com", "mx6.mail.icloud.com"]
    },
    "mail.ru": {
        "type": "generic",
        "imap": ("imap.mail.ru", 993),
        "smtp": ("smtp.mail.ru", 587),
        "auth": "password",
        "domains": ["mail.ru"],
        "mx_servers": ["mxs.mail.ru"]
    },
    "namecheap": {
        "type": "generic",
        "imap": ("mail.privateemail.com", 993),
        "smtp": ("mail.privateemail.com", 587),
        "auth": "password",
        "mx_servers": ["mx1.privateemail.com", "mx2.privateemail.com"]
    },
    "outlook": {
        "type": "generic",
        "imap": ("imap-mail.outlook.com", 993),
        "smtp": ("smtp.live.com", 587),
        "auth": "oauth2",
        "events": False,
        "domains": ["hotmail.com", "outlook.com", "outlook.com.ar",
                    "outlook.com.au", "outlook.at", "outlook.be",
                    "outlook.com.br", "outlook.cl", "outlook.cz", "outlook.dk",
                    "outlook.fr", "outlook.de", "outlook.com.gr",
                    "outlook.co.il", "outlook.in", "outlook.co.id",
                    "outlook.ie", "outlook.it", "outlook.hu", "outlook.jp",
                    "outlook.kr", "outlook.lv", "outlook.my", "outlook.co.nz",
                    "outlook.com.pe", "outlook.ph", "outlook.pt", "outlook.sa",
                    "outlook.sg", "outlook.sk", "outlook.es", "outlook.co.th",
                    "outlook.com.tr", "outlook.com.vn"],
        "mx_servers": [".*.pamx1.hotmail.com"],
    },
    "yahoo": {
        "type": "generic",
        "imap": ("imap.mail.yahoo.com", 993),
        "smtp": ("smtp.mail.yahoo.com", 587),
        "auth": "password",
        "folder_map": {"Bulk Mail": "spam"},
        "domains": ["yahoo.com.ar", "yahoo.com.au", "yahoo.at", "yahoo.be",
                    "yahoo.fr", "yahoo.be", "yahoo.nl", "yahoo.com.br",
                    "yahoo.ca", "yahoo.en", "yahoo.ca", "yahoo.fr",
                    "yahoo.com.cn", "yahoo.cn", "yahoo.com.co", "yahoo.cz",
                    "yahoo.dk", "yahoo.fi", "yahoo.fr", "yahoo.de", "yahoo.gr",
                    "yahoo.com.hk", "yahoo.hu", "yahoo.co.in", "yahoo.in",
                    "yahoo.ie", "yahoo.co.il", "yahoo.it", "yahoo.co.jp",
                    "yahoo.com.my", "yahoo.com.mx", "yahoo.ae", "yahoo.nl",
                    "yahoo.co.nz", "yahoo.no", "yahoo.com.ph", "yahoo.pl",
                    "yahoo.pt", "yahoo.ro", "yahoo.ru", "yahoo.com.sg",
                    "yahoo.co.za", "yahoo.es", "yahoo.se", "yahoo.ch",
                    "yahoo.fr", "yahoo.ch", "yahoo.de", "yahoo.com.tw",
                    "yahoo.co.th", "yahoo.com.tr", "yahoo.co.uk", "yahoo.com",
                    "yahoo.com.vn", "ymail.com", "rocketmail.com"],
        "mx_servers": ["mx-biz.mail.am0.yahoodns.net",
                       "mx1.biz.mail.yahoo.com", "mx5.biz.mail.yahoo.com",
                       "mxvm2.mail.yahoo.com", "mx-van.mail.am0.yahoodns.net"],
    },
    "yandex": {
        "type": "generic",
        "imap": ("imap.yandex.com", 993),
        "smtp": ("smtp.yandex.com", 587),
        "auth": "password",
        "mx_servers": ["mx.yandex.ru"],
    },
    "zimbra": {
        "type": "generic",
        "imap": ("mail.you-got-mail.com", 993),
        "smtp": ("smtp.you-got-mail.com", 587),
        "auth": "password",
        "domains": ["mrmail.com"],
        "mx_servers": ["mx.mrmail.com"]
    },
    "godaddy": {
        "type": "generic",
        "imap": ("imap.secureserver.net", 993),
        "smtp": ("smtpout.secureserver.net", 465),
        "auth": "password",
        "mx_servers": ["mailstore1.secureserver.net",
                       "mailstore1.asia.secureserver.net",
                       "mailstore1.europe.secureserver.net"]
    },
    "custom": {
        "type": "generic",
        "auth": "password"
    }
}


providers = ProvidersDict()
providers.load()
