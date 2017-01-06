"""This module defines strategies for generating test data for IMAP sync, all
well as a mock IMAPClient isntance that can be used to deterministically test
aspects of IMAP sync.
See https://hypothesis.readthedocs.org/en/latest/data.html for more information
about how this works."""
import string

import os
import tempfile
# don't try writing to .hypothesis
os.environ['HYPOTHESIS_STORAGE_DIRECTORY'] = hyp_dir = tempfile.mkdtemp()
os.environ['HYPOTHESIS_DATABASE_FILE'] = os.path.join(hyp_dir, 'db')

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
