from inbox.basicauth import NotSupportedError

__all__ = ['provider_info', 'providers']


def provider_info(provider_name):
    if provider_name not in providers:
        raise NotSupportedError("Provider: {} not supported.".format(
            provider_name))

    return providers[provider_name]


providers = {
    "gmail": {
        "imap": "imap.gmail.com",
        "smtp": "smtp.gmail.com:587",
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
                       "alt4.gmail-smtp-in.l.google.com"],
    },
    "yahoo": {
        "type": "generic",
        "imap": "imap.mail.yahoo.com",
        "smtp": "smtp.mail.yahoo.com:587",
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
    "outlook": {
        "type": "generic",
        "imap": "imap-mail.outlook.com",
        "smtp": "smtp.live.com:587",
        "auth": "oauth2",
        "events": True,
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
    },
    "aol": {
        "type": "generic",
        "imap": "imap.aol.com",
        "smtp": "smtp.aol.com:587",
        "auth": "password",
        "domains": ["aol.com"],
        "mx_servers": ["mailin-01.mx.aol.com", "mailin-02.mx.aol.com",
                       "mailin-03.mx.aol.com", "mailin-04.mx.aol.com"]
    },
    "eas": {
        "auth": "password",
        "domains": [
            "onmicrosoft.com",
            "exchange.mit.edu"
            ],
    },
    "fastmail": {
        "type": "generic",
        "condstore": True,
        "imap": "mail.messagingengine.com",
        "smtp": "mail.messagingengine.com:587",
        "auth": "password",
        "folder_map": {"INBOX.Archive": "archive",
                       "INBOX.Drafts": "drafts", "INBOX.Junk Mail": "spam",
                       "INBOX.Sent Items": "sent", "INBOX.Trash": "trash"},
        "domains": ["fastmail.fm"],
        "mx_servers": ["in1-smtp.messagingengine.com",
                       "in2-smtp.messagingengine.com"],
        "ns_servers": ["ns1.messagingengine.com",
                       "ns2.messagingengine.com"],
    },
    "icloud": {
        "type": "generic",
        "imap": "imap.mail.me.com",
        "smtp": "smtp.mail.me.com:587",
        "auth": "password",
        "events": True,
        "folder_map": {"Sent Messages": "sent",
                       "Deleted Messages": "trash"},
        "domains": ["icloud.com"],
        "mx_servers": ["mx1.mail.icloud.com", "mx2.mail.icloud.com",
                       "mx3.mail.icloud.com", "mx4.mail.icloud.com",
                       "mx5.mail.icloud.com", "mx6.mail.icloud.com"]
    },
    "gmx": {
        "type": "generic",
        "imap": "imap.gmx.com",
        "smtp": "smtp.gmx.com:587",
        "auth": "password",
        "domains": ["gmx.us", "gmx.com"],
    },
    "gandi": {
        "type": "generic",
        "condstore": True,
        "imap": "mail.gandi.net",
        "smtp": "mail.gandi.net:587",
        "auth": "password",
        "domains": ["debuggers.co"],
        "mx_servers": ["spool.mail.gandi.net", "fb.mail.gandi.net",
                       "mail4.gandi.net", "mail5.gandi.net"],
    },
    "zimbra": {
        "type": "generic",
        "imap": "mail.you-got-mail.com",
        "smtp": "smtp.you-got-mail.com:587",
        "auth": "password",
        "domains": ["mrmail.com"],
        "mx_servers": ["mx.mrmail.com"]
    },
    "namecheap": {
        "type": "generic",
        "imap": "mail.privateemail.com",
        "smtp": "mail.privateemail.com:587",
        "auth": "password",
        "mx_servers": ["mx1.privateemail.com", "mx2.privateemail.com"]
    },
    "mail.ru": {
        "type": "generic",
        "imap": "imap.mail.ru",
        "smtp": "smtp.mail.ru:587",
        "auth": "password",
        "domains": ["mail.ru"],
        "mx_servers": ["mxs.mail.ru"]
    }
}
