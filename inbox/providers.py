from __future__ import absolute_import, division, print_function

from inbox.basicauth import NotSupportedError

__all__ = ['provider_info', 'providers']


def provider_info(provider_name):
    """
    Like providers[provider_name] except raises
    inbox.basicauth.NotSupportedError instead of KeyError when the provider is
    not found.

    """
    if provider_name not in providers:
        raise NotSupportedError('Provider: {} not supported.'.format(
            provider_name))

    return providers[provider_name]


providers = dict([
    ("aol", {
        "type": "generic",
        "imap": ("imap.aol.com", 993),
        "smtp": ("smtp.aol.com", 587),
        "auth": "password",
        # .endswith() string match
        "domains": ["aol.com"],
        # regex match with dots interpreted literally and glob * as .*,
        # pinned to start and end
        "mx_servers": ["mailin-0[1-4].mx.aol.com"],
    }),
    ("bluehost", {
        "type": "generic",
        "auth": "password",
        "domains": ["autobizbrokers.com"],
    }),
    ("eas", {
        "auth": "password",
        "domains": [
            "onmicrosoft.com",
            "exchange.mit.edu",
            "savills-studley.com",
            "clearpoolgroup.com",
            "stsci.edu",
            "kms-technology.com",
            "cigital.com",
            "iontrading.com",
            "adaptiveinsights.com",
            "icims.com",
        ],
        "mx_servers": [
            # Office365
            "*.mail.protection.outlook.com", "*.mail.eo.outlook.com",
        ],
    }),
    ("outlook", {
        "auth": "password",
        "domains": [
            "outlook.com", "outlook.com.ar",
            "outlook.com.au", "outlook.at", "outlook.be",
            "outlook.com.br", "outlook.cl", "outlook.cz", "outlook.dk",
            "outlook.fr", "outlook.de", "outlook.com.gr",
            "outlook.co.il", "outlook.in", "outlook.co.id",
            "outlook.ie", "outlook.it", "outlook.hu", "outlook.jp",
            "outlook.kr", "outlook.lv", "outlook.my", "outlook.co.nz",
            "outlook.com.pe", "outlook.ph", "outlook.pt", "outlook.sa",
            "outlook.sg", "outlook.sk", "outlook.es", "outlook.co.th",
            "outlook.com.tr", "outlook.com.vn", "live.com", "live.com.ar"
            "live.com.au", "live.at", "live.be", "live.cl", "live.cz",
            "live.dk", "live.fr", "live.de", "live.com.gr", "live.co.il",
            "live.in", "live.ie", "live.it", "live.hu", "live.jp", "live.lv",
            "live.co.nz", "live.com.pe", "live.ph", "live.pt", "live.sa",
            "live.sg", "live.sk", "live.es", "live.co.th", "live.com.tr",
            "live.com.vn", "live.ca", "hotmail.ca",
            "hotmail.com", "hotmail.com.ar", "hotmail.com.au",
            "hotmail.at", "hotmail.be", "hotmail.com.br", "hotmail.cl",
            "hotmail.cz", "hotmail.dk", "hotmail.fr", "hotmail.de",
            "hotmail.co.il", "hotmail.in", "hotmail.ie", "hotmail.it",
            "hotmail.hu", "hotmail.jp", "hotmail.kr", "hotmail.com.pe",
            "hotmail.pt", "hotmail.sa", "hotmail.es", "hotmail.co.th",
            "hotmail.com.tr",
        ],
        "mx_servers": [
            "*.pamx1.hotmail.com", "mx.*.hotmail.com",
        ]
    }),
    ("_outlook", {
        # IMAP-based Outlook. Legacy-only.
        "type": "generic",
        "imap": ("imap-mail.outlook.com", 993),
        "smtp": ("smtp.live.com", 587),
        "auth": "oauth2",
        "events": False,
    }),
    ("fastmail", {
        "type": "generic",
        "condstore": True,
        "imap": ("imap.fastmail.com", 993),
        "smtp": ("smtp.fastmail.com", 465),
        "auth": "password",
        "folder_map": {"INBOX.Archive": "archive",
                       "INBOX.Drafts": "drafts", "INBOX.Junk Mail": "spam",
                       "INBOX.Sent": "sent", "INBOX.Sent Items": "sent",
                       "INBOX.Trash": "trash"},
        "domains": ["fastmail.fm", "fastmail.com"],
        "mx_servers": ["in[12]-smtp.messagingengine.com"],
        # exact string matches
        "ns_servers": ["ns1.messagingengine.com.",
                       "ns2.messagingengine.com."],
    }),
    ("gandi", {
        "type": "generic",
        "condstore": True,
        "imap": ("mail.gandi.net", 993),
        "smtp": ("mail.gandi.net", 587),
        "auth": "password",
        "domains": ["debuggers.co"],
        "mx_servers": ["(spool|fb).mail.gandi.net", "mail[45].gandi.net"],
    }),
    ("gmx", {
        "type": "generic",
        "imap": ("imap.gmx.com", 993),
        "smtp": ("smtp.gmx.com", 587),
        "auth": "password",
        "domains": ["gmx.us", "gmx.com"],
    }),
    ("hover", {
        "type": "generic",
        "imap": ("mail.hover.com", 993),
        "smtp": ("mail.hover.com", 587),
        "auth": "password",
        "mx_servers": ["mx.hover.com.cust.hostedemail.com"],
    }),
    ("icloud", {
        "type": "generic",
        "imap": ("imap.mail.me.com", 993),
        "smtp": ("smtp.mail.me.com", 587),
        "auth": "password",
        "events": False,
        "contacts": True,
        "folder_map": {"Sent Messages": "sent",
                       "Deleted Messages": "trash"},
        "domains": ["icloud.com"],
        "mx_servers": ["mx[1-6].mail.icloud.com"]
    }),
    ("soverin", {
        "type": "generic",
        "imap": ("imap.soverin.net", 993),
        "smtp": ("smtp.soverin.net", 587),
        "auth": "password",
        "domains": ["soverin.net"],
        "mx_servers": ["mx.soverin.net"]
    }),
    ("mail.ru", {
        "type": "generic",
        "imap": ("imap.mail.ru", 993),
        "smtp": ("smtp.mail.ru", 587),
        "auth": "password",
        "domains": ["mail.ru"],
        "mx_servers": ["mxs.mail.ru"]
    }),
    ("namecheap", {
        "type": "generic",
        "imap": ("mail.privateemail.com", 993),
        "smtp": ("mail.privateemail.com", 465),
        "auth": "password",
        "mx_servers": ["mx[12].privateemail.com"]
    }),
    ("tiliq", {
        "type": "generic",
        "imap": ("imap.us-west-2.tiliq.com", 993),
        "smtp": ("smtp.tiliq.com", 587),
        "auth": "password",
        "mx_servers": ["mx[12].(us-west-2.)?tiliq.com"]
    }),
    ("yahoo", {
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
                       "mx[15].biz.mail.yahoo.com",
                       "mxvm2.mail.yahoo.com", "mx-van.mail.am0.yahoodns.net"],
    }),
    ("yandex", {
        "type": "generic",
        "imap": ("imap.yandex.com", 993),
        "smtp": ("smtp.yandex.com", 587),
        "auth": "password",
        "mx_servers": ["mx.yandex.ru"],
    }),
    ("zimbra", {
        "type": "generic",
        "imap": ("mail.you-got-mail.com", 993),
        "smtp": ("smtp.you-got-mail.com", 587),
        "auth": "password",
        "domains": ["mrmail.com"],
        "mx_servers": ["mx.mrmail.com"]
    }),
    ("godaddy", {
        "type": "generic",
        "imap": ("imap.secureserver.net", 993),
        "smtp": ("smtpout.secureserver.net", 465),
        "auth": "password",
        "mx_servers": ["smtp.secureserver.net",
                       "mailstore1.(asia.|europe.)?secureserver.net"]
    }),
    ("163", {
        "type": "generic",
        "imap": ("imap.163.com", 993),
        "smtp": ("smtp.163.com", 465),
        "auth": "password",
        "domains": ["163.com"],
        "mx_servers": ["163mx0[0-3].mxmail.netease.com"]
    }),
    ("163_ym", {
        "type": "generic",
        "imap": ("imap.ym.163.com", 993),
        "smtp": ("smtp.ym.163.com", 994),
        "auth": "password",
        "mx_servers": ["mx.ym.163.com"]
    }),
    ("163_qiye", {
        "type": "generic",
        "imap": ("imap.qiye.163.com", 993),
        "smtp": ("smtp.qiye.163.com", 994),
        "auth": "password",
        "mx_servers": ["qiye163mx0[12].mxmail.netease.com"]
    }),
    ("123_reg", {
        "type": "generic",
        "imap": ("imap.123-reg.co.uk", 993),
        "smtp": ("smtp.123-reg.co.uk", 465),
        "auth": "password",
        "mx_servers": ["mx[01].123-reg.co.uk"]
    }),
    ("126", {
        "type": "generic",
        "imap": ("imap.126.com", 993),
        "smtp": ("smtp.126.com", 465),
        "auth": "password",
        "domains": ["126.com"],
        "mx_servers": ["126mx0[0-2].mxmail.netease.com"]
    }),
    ("yeah.net", {
        "type": "generic",
        "imap": ("imap.yeah.net", 993),
        "smtp": ("smtp.yeah.net", 465),
        "auth": "password",
        "domains": ["yeah.net"],
        "mx_servers": ["yeahmx0[01].mxmail.netease.com"]
    }),
    ("qq", {
        "type": "generic",
        "imap": ("imap.qq.com", 993),
        "smtp": ("smtp.qq.com", 465),
        "auth": "password",
        "domains": ["qq.com", "vip.qq.com"],
        "mx_servers": ["mx[1-3].qq.com"]
    }),
    ("foxmail", {
        "type": "generic",
        "imap": ("imap.exmail.qq.com", 993),
        "smtp": ("smtp.exmail.qq.com", 465),
        "auth": "password",
        "domains": ["foxmail.com"],
        "mx_servers": ["mx[1-3].qq.com"]
    }),
    ("qq_enterprise", {
        "type": "generic",
        "imap": ("imap.exmail.qq.com", 993),
        "smtp": ("smtp.exmail.qq.com", 465),
        "auth": "password",
        "mx_servers": ["mxbiz[12].qq.com"]
    }),
    ("aliyun", {
        "type": "generic",
        "imap": ("imap.aliyun.com", 993),
        "smtp": ("smtp.aliyun.com", 465),
        "auth": "password",
        "domains": ["aliyun"],
        "mx_servers": ["mx2.mail.aliyun.com"]
    }),
    ("139", {
        "type": "generic",
        "imap": ("imap.139.com", 993),
        "smtp": ("smtp.139.com", 465),
        "auth": "password",
        "domains": ["139.com"],
        "mx_servers": ["mx[1-3].mail.139.com"]
    }),
    ("gmail", {
        "imap": ("imap.gmail.com", 993),
        "smtp": ("smtp.gmail.com", 587),
        "auth": "oauth2",
        "events": True,
        "contacts": True,
        "mx_servers": ["aspmx.l.google.com",
                       "aspmx[2-6].googlemail.com",
                       "(alt|aspmx)[1-4].aspmx.l.google.com",
                       "gmail-smtp-in.l.google.com",
                       "alt[1-4].gmail-smtp-in.l.google.com",
                       # Postini
                       "*.psmtp.com"],
    }),
    ("custom", {
        "type": "generic",
        "auth": "password",
        "folder_map": {"INBOX.Archive": "archive",
                       "INBOX.Drafts": "drafts", "INBOX.Junk Mail": "spam",
                       "INBOX.Trash": "trash", "INBOX.Sent Items": "sent",
                       "INBOX.Sent": "sent"},
    })
])
