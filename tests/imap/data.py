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


def build_uid_data(internaldate, flags, body, g_labels, g_msgid, modseq):
    return {
        'INTERNALDATE': internaldate,
        'FLAGS': flags,
        'BODY[]': body,
        'RFC822.SIZE': len(body),
        'X-GM-LABELS': g_labels,
        'X-GM-MSGID': g_msgid,
        'X-GM-THRID': g_msgid,  # For simplicity
        'MODSEQ': modseq
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
    max_size=5
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
    randint,
    randint)


uids = s.dictionaries(
    s.integers(min_value=22),
    uid_data,
    min_size=5,
    max_size=10)


class MockIMAPClient(object):
    """A bare-bones stand-in for an IMAPClient instance, used to test sync
    logic without requiring a real IMAP account and server."""

    def __init__(self):
        self._data = {}
        self.selected_folder = None
        self.uidvalidity = 1

    def idle_check(self, timeout=None):
        return []

    def idle_done(self):
        return ('Idle terminated', [])

    def add_folder_data(self, folder_name, uids):
        """Adds fake UID data for the given folder."""
        self._data[folder_name] = uids

    def search(self, criteria):
        assert self.selected_folder is not None
        assert isinstance(criteria, list)
        uid_dict = self._data[self.selected_folder]
        if criteria == ['ALL']:
            return uid_dict.keys()
        if criteria == ['X-GM-LABELS', 'inbox']:
            return [k for k, v in uid_dict.items()
                    if ('\\Inbox,') in v['X-GM-LABELS']]
        if criteria[0] == 'HEADER':
            name, value = criteria[1:]
            headerstring = '{}: {}'.format(name, value).lower()
            # Slow implementation, but whatever
            return [u for u, v in uid_dict.items() if headerstring in
                    v['BODY[]'].lower()]
        if criteria[0] == 'X-GM-THRID':
            assert len(criteria) == 2
            thrid = criteria[1]
            return [u for u, v in uid_dict.items() if v['X-GM-THRID'] == thrid]
        raise ValueError('unsupported test criteria: {!r}'.format(criteria))

    def select_folder(self, folder_name, readonly=False):
        self.selected_folder = folder_name
        return self.folder_status(folder_name)

    def fetch(self, items, data, modifiers=None):
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
            if modifiers is not None:
                m = re.match('CHANGEDSINCE (?P<modseq>[0-9]+)', modifiers[0])
                if m:
                    modseq = int(m.group('modseq'))
                    items = {u for u in items
                             if uid_dict[u]['MODSEQ'][0] > modseq}
        for u in items:
            if u in uid_dict:
                resp[u] = {k: v for k, v in uid_dict[u].items() if k in data or
                           k == 'MODSEQ'}
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

    def copy(self, matching_uids, folder_name):
        """
        Note: _moves_ one or more messages from the currently selected folder
        to folder_name
        """
        for u in matching_uids:
            self._data[folder_name][u] = self._data[self.selected_folder][u]
        self.delete_messages(matching_uids)

    def capabilities(self):
        return []

    def folder_status(self, folder_name, data=None):
        folder_data = self._data[folder_name]
        lastuid = max(folder_data) if folder_data else 0
        resp = {
            'UIDNEXT': lastuid + 1,
            'UIDVALIDITY': self.uidvalidity
        }
        if data and 'HIGHESTMODSEQ' in data:
            resp['HIGHESTMODSEQ'] = max(v['MODSEQ'] for v in
                                        folder_data.values())
        return resp

    def delete_messages(self, uids):
        for u in uids:
            del self._data[self.selected_folder][u]

    def expunge(self):
        pass


@pytest.fixture
def mock_imapclient(monkeypatch):
    conn = MockIMAPClient()
    monkeypatch.setattr(
        'inbox.crispin.CrispinConnectionPool._new_raw_connection',
        lambda *args: conn
    )
    return conn
