"""
Basic tests for GmailCrispinClient/CrispinClient methods. We replace
imapclient.IMAPClient._imap by a mock in order to test these. In particular, we
want to test that we handle unsolicited FETCH responses, which may be returned
by some providers (Gmail, Fastmail).
"""
from datetime import datetime
import mock
import imapclient
import pytest
from inbox.crispin import (CrispinClient, GmailCrispinClient, GMetadata,
                           GmailFlags, RawMessage, Flags)


class MockedIMAPClient(imapclient.IMAPClient):
    def _create_IMAP4(self):
        return mock.Mock()


@pytest.fixture
def gmail_client():
    conn = MockedIMAPClient(host='somehost')
    return GmailCrispinClient(account_id=1, provider_info=None,
                              email_address='inboxapptest@gmail.com',
                              conn=conn)


@pytest.fixture
def generic_client():
    conn = MockedIMAPClient(host='somehost')
    return CrispinClient(account_id=1, provider_info=None,
                         email_address='inboxapptest@fastmail.fm', conn=conn)


@pytest.fixture
def constants():
    g_msgid = 1494576757102068682
    g_thrid = 1494576757102068682
    seq = 1231
    uid = 1764
    modseq = 95020
    flags = ()
    g_labels = ()
    internaldate = '02-Mar-2015 23:36:20 +0000'
    body = 'Delivered-To: ...'
    body_size = len(body)
    return dict(g_msgid=g_msgid, g_thrid=g_thrid, seq=seq, uid=uid,
                modseq=modseq, flags=flags, g_labels=g_labels,
                body=body, body_size=body_size, internaldate=internaldate)


def patch_imap4(crispin_client, resp):
    crispin_client.conn._imap._command_complete.return_value = (
        'OK', ['Success'])
    crispin_client.conn._imap._untagged_response.return_value = ('OK', resp)


def test_g_metadata(gmail_client, constants):
    expected_resp = '{seq} (X-GM-THRID {g_thrid} X-GM-MSGID {g_msgid} ' \
                    'UID {uid} MODSEQ ({modseq}))'.format(**constants)
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(gmail_client, [expected_resp, unsolicited_resp])
    uid = constants['uid']
    g_msgid = constants['g_msgid']
    g_thrid = constants['g_thrid']
    assert gmail_client.g_metadata([uid]) == {uid: GMetadata(g_msgid, g_thrid)}


def test_gmail_flags(gmail_client, constants):
    expected_resp = '{seq} (FLAGS {flags} X-GM-LABELS {g_labels} ' \
                    'UID {uid} MODSEQ ({modseq}))'.format(**constants)
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(gmail_client, [expected_resp, unsolicited_resp])
    uid = constants['uid']
    flags = constants['flags']
    g_labels = constants['g_labels']
    assert gmail_client.flags([uid]) == {uid: GmailFlags(flags, g_labels)}


def test_g_msgids(gmail_client, constants):
    expected_resp = '{seq} (X-GM-MSGID {g_msgid} ' \
                    'UID {uid} MODSEQ ({modseq}))'.format(**constants)
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(gmail_client, [expected_resp, unsolicited_resp])
    uid = constants['uid']
    g_msgid = constants['g_msgid']
    assert gmail_client.g_msgids([uid]) == {uid: g_msgid}


def test_gmail_body(gmail_client, constants):
    expected_resp = ('{seq} (X-GM-MSGID {g_msgid} X-GM-THRID {g_thrid} '
                     'X-GM-LABELS {g_labels} UID {uid} MODSEQ ({modseq}) '
                     'INTERNALDATE "{internaldate}" FLAGS {flags} '
                     'BODY[] {{{body_size}}}'.format(**constants),
                     constants['body'])
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(gmail_client, [expected_resp, ')', unsolicited_resp])

    uid = constants['uid']
    flags = constants['flags']
    g_labels = constants['g_labels']
    g_thrid = constants['g_thrid']
    g_msgid = constants['g_msgid']
    body = constants['body']
    assert gmail_client.uids([uid]) == [
        RawMessage(uid=uid,
                   internaldate=datetime(2015, 3, 2, 23, 36, 20),
                   flags=flags,
                   body=body,
                   g_labels=g_labels,
                   g_thrid=g_thrid,
                   g_msgid=g_msgid)
    ]


def test_flags(generic_client, constants):
    expected_resp = '{seq} (FLAGS {flags} ' \
                    'UID {uid} MODSEQ ({modseq}))'.format(**constants)
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(generic_client, [expected_resp, unsolicited_resp])
    uid = constants['uid']
    flags = constants['flags']
    assert generic_client.flags([uid]) == {uid: Flags(flags)}


def test_body(generic_client, constants):
    expected_resp = ('{seq} (UID {uid} MODSEQ ({modseq}) '
                     'INTERNALDATE "{internaldate}" FLAGS {flags} '
                     'BODY[] {{{body_size}}}'.format(**constants),
                     constants['body'])
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(generic_client, [expected_resp, ')', unsolicited_resp])

    uid = constants['uid']
    flags = constants['flags']
    body = constants['body']
    assert generic_client.uids([uid]) == [
        RawMessage(uid=uid,
                   internaldate=datetime(2015, 3, 2, 23, 36, 20),
                   flags=flags,
                   body=body,
                   g_labels=None,
                   g_thrid=None,
                   g_msgid=None)
    ]
