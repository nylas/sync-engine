"""This module defines strategies for generating test data for IMAP sync, all
well as a mock IMAPClient isntance that can be used to deterministically test
aspects of IMAP sync.
See https://hypothesis.readthedocs.org/en/latest/data.html for more information
about how this works."""
import re
import string
import pytest
from hypothesis import strategies as s
from hypothesis.extra.datetime import datetimes
import flanker
from flanker import mime


def _build_address_header(addresslist):
    return ', '.join(
        flanker.addresslib.address.EmailAddress(phrase, spec).full_spec()
        for phrase, spec in addresslist
    )


def build_mime_message(from_, to, cc, bcc, subject, body):
    msg = mime.create.multipart('alternative')
    msg.append(
        mime.create.text('plain', body)
    )
    msg.headers['Subject'] = subject
    msg.headers['From'] = _build_address_header(from_)
    msg.headers['To'] = _build_address_header(to)
    msg.headers['Cc'] = _build_address_header(cc)
    msg.headers['Bcc'] = _build_address_header(bcc)
    return msg.to_string()


def build_uid_data(internaldate, flags, body, g_labels, g_msgid):
    return {
        'INTERNALDATE': internaldate,
        'FLAGS': flags,
        'BODY[]': body,
        'RFC822.SIZE': len(body),
        'X-GM-LABELS': g_labels,
        'X-GM-MSGID': g_msgid,
        'X-GM-THRID': g_msgid  # For simplicity
    }


# We don't want to worry about whacky encodings or pathologically long data
# here, so just generate some basic, sane ASCII text.
basic_text = s.text(string.ascii_letters, min_size=1, max_size=64)


# An email address of the form 'foo@bar'.
address = s.builds(
    lambda localpart, domain: '{}@{}'.format(localpart, domain),
    basic_text, basic_text)


# A list of tuples ('displayname', 'addr@domain')
addresslist = s.lists(
    s.tuples(basic_text, address),
    min_size=1,
    max_size=10
)


# A basic MIME message with plaintext body plus From/To/Cc/Bcc/Subject headers
mime_message = s.builds(
    build_mime_message,
    addresslist,
    addresslist,
    addresslist,
    addresslist,
    basic_text,
    basic_text
)

randint = s.basic(generate=lambda random, _: random.getrandbits(63))

uid_data = s.builds(
    build_uid_data,
    datetimes(timezones=[]),
    s.sampled_from([(), ('\\Seen',)]),
    mime_message,
    s.sampled_from([(), ('\\Inbox',)]),
    randint)


uids = s.dictionaries(
    s.integers(min_value=22),
    uid_data,
    min_size=24)


class MockIMAPClient(object):
    """A bare-bones stand-in for an IMAPClient instance, used to test sync
    logic without requiring a real IMAP account and server."""
    def __init__(self):
        self._data = {}
        self.selected_folder = None
        self.uidvalidity = 1

    def add_folder_data(self, folder_name, uids):
        """Adds fake UID data for the given folder."""
        self._data[folder_name] = uids

    def search(self, criteria):
        assert self.selected_folder is not None
        uid_dict = self._data[self.selected_folder]
        if criteria == ['ALL']:
            return uid_dict.keys()
        if criteria == ['X-GM-LABELS inbox']:
            return [k for k, v in uid_dict.items()
                    if ('\\Inbox,') in v['X-GM-LABELS']]

        m = re.match('HEADER (?P<name>[a-zA-Z-]+) (?P<value>.+)', criteria[0])
        if m:
            name = m.group('name').lower()
            value = m.group('value').lower()
            headerstring = '{}: {}'.format(name, value)
            # Slow implementation, but whatever
            return [u for u, v in uid_dict.items() if headerstring in
                    v['BODY[]'].lower()]

        if re.match('X-GM-THRID [0-9]*', criteria[0]):
            thrid = int(criteria[0].split()[1])
            return [u for u, v in uid_dict.items() if v['X-GM-THRID'] == thrid]

    def select_folder(self, folder_name, readonly):
        self.selected_folder = folder_name
        return self.folder_status(folder_name)

    def fetch(self, items, data):
        assert self.selected_folder is not None
        uid_dict = self._data[self.selected_folder]
        resp = {}
        if 'BODY.PEEK[]' in data:
            data.remove('BODY.PEEK[]')
            data.append('BODY[]')
        if isinstance(items, (int, long)):
            items = [items]
        elif isinstance(items, basestring) and re.match('[0-9]+:\*', items):
            min_uid = int(items.split(':')[0])
            items = {u for u in uid_dict if u >= min_uid} | {max(uid_dict)}
        for u in items:
            if u in uid_dict:
                resp[u] = {k: v for k, v in uid_dict[u].items() if k in data}
        return resp

    def append(self, folder_name, mimemsg, flags, date):
        uid_dict = self._data[folder_name]
        uidnext = max(uid_dict) if uid_dict else 1
        uid_dict[uidnext] = {
            # TODO(emfree) save other attributes
            'BODY[]': mimemsg,
            'INTERNALDATE': None,
            'X-GM-LABELS': (),
            'FLAGS': (),
            'X-GM-MSGID': 0,
            'X-GM-THRID': 0
        }

    def capabilities(self):
        return []

    def folder_status(self, folder_name, data=None):
        folder_data = self._data[folder_name]
        lastuid = max(folder_data) if folder_data else 0
        return {
            'UIDNEXT': lastuid + 1,
            'UIDVALIDITY': self.uidvalidity
        }

    def delete_messages(self, uids):
        for u in uids:
            del self._data[self.selected_folder_name][u]


@pytest.fixture
def mock_imapclient(monkeypatch):
    conn = MockIMAPClient()
    monkeypatch.setattr(
        'inbox.crispin.CrispinConnectionPool._new_raw_connection',
        lambda *args: conn
    )
    return conn
