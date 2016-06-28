# -*- coding: utf-8 -*-
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
                           GmailFlags, RawMessage, Flags,
                           FolderMissingError, localized_folder_names)


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
    # Global constants.
    g_msgid = 1494576757102068682
    g_thrid = 1494576757102068682
    seq = 1231
    uid = 1764
    modseq = 95020
    size = 16384
    flags = ()
    raw_g_labels = '(mot&APY-rhead &A7wDtQPEA6wDvQO,A7kDsQ- \\Inbox)'
    unicode_g_labels = [u'motörhead', u'μετάνοια', '\\Inbox']

    internaldate = '02-Mar-2015 23:36:20 +0000'
    body = 'Delivered-To: ...'
    body_size = len(body)

    # folder test constant
    gmail_role_map = {
        '[Gmail]/All Mail': 'all',
        'Inbox': 'inbox',
        '[Gmail]/Trash': 'trash',
        '[Gmail]/Spam': 'spam',
        '[Gmail]/Drafts': 'drafts',
        '[Gmail]/Sent Mail': 'sent',
        '[Gmail]/Important': 'important',
        '[Gmail]/Starred': 'starred',
        'reference': None
    }

    gmail_folders = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'[Gmail]'),
         (('\\HasNoChildren', '\\All'), '/', u'[Gmail]/All Mail'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'[Gmail]/Drafts'),
         (('\\HasNoChildren', '\\Important'), '/', u'[Gmail]/Important'),
         (('\\HasNoChildren', '\\Sent'), '/', u'[Gmail]/Sent Mail'),
         (('\\HasNoChildren', '\\Junk'), '/', u'[Gmail]/Spam'),
         (('\\Flagged', '\\HasNoChildren'), '/', u'[Gmail]/Starred'),
         (('\\HasNoChildren', '\\Trash'), '/', u'[Gmail]/Trash'),
         (('\\HasNoChildren',), '/', u'reference')]
    imap_folders = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'SKIP'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'Drafts'),
         (('\\HasNoChildren', '\\Sent'), '/', u'Sent'),
         (('\\HasNoChildren', '\\Sent'), '/', u'Sent Items'),
         (('\\HasNoChildren', '\\Junk'), '/', u'Spam'),
         (('\\HasNoChildren', '\\Trash'), '/', u'Trash'),
         (('\\HasNoChildren',), '/', u'reference')]

    imap_role_map = {
        'INBOX': 'inbox',
        'Trash': 'trash',
        'Drafts': 'drafts',
        'Sent': 'sent',
        'Sent Items': 'sent',
        'Spam': 'spam',
        u'reference': None
    }
    return dict(g_msgid=g_msgid, g_thrid=g_thrid, seq=seq, uid=uid,
                modseq=modseq, size=size, flags=flags,
                raw_g_labels=raw_g_labels, unicode_g_labels=unicode_g_labels,
                body=body, body_size=body_size, internaldate=internaldate,
                gmail_role_map=gmail_role_map, gmail_folders=gmail_folders,
                imap_role_map=imap_role_map, imap_folders=imap_folders)


def patch_gmail_client(monkeypatch, folders):
    monkeypatch.setattr(GmailCrispinClient, '_fetch_folder_list',
                        lambda x: folders)

    conn = MockedIMAPClient(host='somehost')
    return GmailCrispinClient(account_id=1, provider_info=None,
                              email_address='inboxapptest@gmail.com',
                              conn=conn)


def patch_generic_client(monkeypatch, folders):
    monkeypatch.setattr(CrispinClient, '_fetch_folder_list',
                        lambda x: folders)

    conn = MockedIMAPClient(host='somehost')
    return CrispinClient(account_id=1, provider_info={},
                         email_address='inboxapptest@fastmail.fm', conn=conn)


def patch_imap4(crispin_client, resp):
    crispin_client.conn._imap._command_complete.return_value = (
        'OK', ['Success'])
    crispin_client.conn._imap._untagged_response.return_value = ('OK', resp)


def test_g_metadata(gmail_client, constants):
    expected_resp = '{seq} (X-GM-THRID {g_thrid} X-GM-MSGID {g_msgid} ' \
                    'RFC822.SIZE {size} UID {uid} MODSEQ ({modseq}))'. \
                    format(**constants)
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(gmail_client, [expected_resp, unsolicited_resp])
    uid = constants['uid']
    g_msgid = constants['g_msgid']
    g_thrid = constants['g_thrid']
    size = constants['size']
    assert gmail_client.g_metadata([uid]) == {uid: GMetadata(g_msgid, g_thrid,
                                                             size)}


def test_gmail_flags(gmail_client, constants):
    expected_resp = '{seq} (FLAGS {flags} X-GM-LABELS {raw_g_labels} ' \
                    'UID {uid} MODSEQ ({modseq}))'.format(**constants)
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(gmail_client, [expected_resp, unsolicited_resp])
    uid = constants['uid']
    flags = constants['flags']
    modseq = constants['modseq']
    g_labels = constants['unicode_g_labels']
    assert gmail_client.flags([uid]) == {uid: GmailFlags(flags, g_labels,
                                                         modseq)}


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
                     'X-GM-LABELS {raw_g_labels} UID {uid} MODSEQ ({modseq}) '
                     'INTERNALDATE "{internaldate}" FLAGS {flags} '
                     'BODY[] {{{body_size}}}'.format(**constants),
                     constants['body'])
    unsolicited_resp = '1198 (UID 1731 MODSEQ (95244) FLAGS (\\Seen))'
    patch_imap4(gmail_client, [expected_resp, ')', unsolicited_resp])

    uid = constants['uid']
    flags = constants['flags']
    g_labels = constants['unicode_g_labels']
    g_thrid = constants['g_thrid']
    g_msgid = constants['g_msgid']
    body = constants['body']
    assert gmail_client.uids([uid]) == [
        RawMessage(uid=long(uid),
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
    assert generic_client.flags([uid]) == {uid: Flags(flags, None)}


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
        RawMessage(uid=long(uid),
                   internaldate=datetime(2015, 3, 2, 23, 36, 20),
                   flags=flags,
                   body=body,
                   g_labels=None,
                   g_thrid=None,
                   g_msgid=None)
    ]


def test_internaldate(generic_client, constants):
    """ Test that our monkeypatched imaplib works through imapclient """
    dates_to_test = [
        ('6-Mar-2015 10:02:32 +0900', datetime(2015, 3, 6, 1, 2, 32)),
        (' 6-Mar-2015 10:02:32 +0900', datetime(2015, 3, 6, 1, 2, 32)),
        ('06-Mar-2015 10:02:32 +0900', datetime(2015, 3, 6, 1, 2, 32)),
        ('6-Mar-2015 07:02:32 +0900', datetime(2015, 3, 5, 22, 2, 32)),
        (' 3-Sep-1922 09:16:51 +0000', datetime(1922, 9, 3, 9, 16, 51)),
        ('2-Jan-2015 03:05:37 +0800', datetime(2015, 1, 1, 19, 5, 37))
    ]

    for internaldate_string, native_date in dates_to_test:
        constants['internaldate'] = internaldate_string
        expected_resp = ('{seq} (UID {uid} MODSEQ ({modseq}) '
                         'INTERNALDATE "{internaldate}" FLAGS {flags} '
                         'BODY[] {{{body_size}}}'.format(**constants),
                         constants['body'])
        patch_imap4(generic_client, [expected_resp, ')'])

        uid = constants['uid']
        assert generic_client.uids([uid]) == [
            RawMessage(uid=long(uid),
                       internaldate=native_date,
                       flags=constants['flags'],
                       body=constants['body'],
                       g_labels=None,
                       g_thrid=None,
                       g_msgid=None)
        ]


def test_deleted_folder_on_select(monkeypatch, generic_client, constants):
    """ Test that a 'select failed EXAMINE' error specifying that a folder
        doesn't exist is converted into a FolderMissingError. (Yahoo style)
    """
    def raise_invalid_folder_exc(*args, **kwargs):
        raise imapclient.IMAPClient.Error("select failed: '[TRYCREATE] EXAMINE"
                                          " error - Folder does not exist or"
                                          " server encountered an error")

    monkeypatch.setattr('imapclient.IMAPClient.select_folder',
                        raise_invalid_folder_exc)

    with pytest.raises(FolderMissingError):
        generic_client.select_folder('missing_folder', lambda: True)


def test_deleted_folder_on_fetch(monkeypatch, generic_client, constants):
    """ Test that a 'select failed EXAMINE' error specifying that a folder
        doesn't exist is converted into a FolderMissingError. (Yahoo style)
    """
    def raise_invalid_uid_exc(*args, **kwargs):
        raise imapclient.IMAPClient.Error(
            '[UNAVAILABLE] UID FETCH Server error while fetching messages')

    monkeypatch.setattr('imapclient.IMAPClient.fetch',
                        raise_invalid_uid_exc)

    # Simply check that the Error exception is handled.
    generic_client.uids(["125"])


def test_gmail_folders(monkeypatch, constants):
    folders = constants['gmail_folders']
    role_map = constants['gmail_role_map']

    client = patch_gmail_client(monkeypatch, folders)

    raw_folders = client.folders()
    generic_folder_checks(raw_folders, role_map, client, 'gmail')


def generic_folder_checks(raw_folders, role_map, client, provider):

    # Should not contain the `\\Noselect' folder
    assert filter(lambda y: '\\Noselect' in y,
                  map(lambda x: x[0], raw_folders)) == []
    if provider == 'gmail':
        assert {f.display_name: f.role for f in raw_folders} == role_map
    elif provider == 'imap':
        for f in raw_folders:
            if f.display_name in role_map:
                assert f.role == role_map[f.display_name]
            else:
                assert f.display_name in ['reference']
                assert f.role is None

    folder_names = client.folder_names()
    if provider == 'gmail':
        for role in ['inbox', 'all', 'trash', 'drafts', 'important', 'sent',
                     'spam', 'starred']:
            assert role in folder_names

            names = folder_names[role]
            assert isinstance(names, list) and len(names) == 1
    elif provider == 'imap':
        for role in ['inbox', 'trash', 'drafts', 'sent', 'spam']:
            assert role in folder_names

            names = folder_names[role]
            assert isinstance(names, list)

            if role == 'sent':
                assert len(names) == 2
            else:
                assert len(names) == 1
                # Inbox folder should be synced first.
                assert client.sync_folders()[0] == 'INBOX'


def test_gmail_missing_trash(constants, monkeypatch):
    '''
    Test that we can label their folder when they
    don't have a folder labeled trash. This test will go through a list
    of examples of trash aliases we have seen in the wild,
    and check that we are able to properly label those folders.
    '''
    # create list of folders that doesn't have a trash folder
    folder_base = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'[Gmail]'),
         (('\\HasNoChildren', '\\All'), '/', u'[Gmail]/All Mail'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'[Gmail]/Drafts'),
         (('\\HasNoChildren', '\\Important'), '/', u'[Gmail]/Important'),
         (('\\HasNoChildren', '\\Sent'), '/', u'[Gmail]/Sent Mail'),
         (('\\HasNoChildren', '\\Junk'), '/', u'[Gmail]/Spam'),
         (('\\Flagged', '\\HasNoChildren'), '/', u'[Gmail]/Starred'),
         (('\\HasNoChildren',), '/', u'reference')]
    check_missing_generic('trash',
                          folder_base, localized_folder_names['trash'],
                          'gmail', constants, monkeypatch)


def test_imap_missing_trash(constants, monkeypatch):
    '''
    Same strategy as test_gmail_missing_trash, except with imap as a provider
    '''
    folder_base = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'SKIP'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'Drafts'),
         (('\\HasNoChildren', '\\Sent'), '/', u'Sent'),
         (('\\HasNoChildren', '\\Sent'), '/', u'Sent Items'),
         (('\\HasNoChildren', '\\Junk'), '/', u'Spam'),
         (('\\HasNoChildren',), '/', u'reference')]
    check_missing_generic('trash',
                          folder_base, localized_folder_names['trash'],
                          'imap', constants, monkeypatch)


def test_gmail_missing_spam(constants, monkeypatch):
    '''
    Same strategy as test_gmail_missing_trash, except with spam folder aliases
    '''
    # Create a list of folders thath doesn't have a spam folder
    folder_base = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'[Gmail]'),
         (('\\HasNoChildren', '\\All'), '/', u'[Gmail]/All Mail'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'[Gmail]/Drafts'),
         (('\\HasNoChildren', '\\Important'), '/', u'[Gmail]/Important'),
         (('\\HasNoChildren', '\\Sent'), '/', u'[Gmail]/Sent Mail'),
         (('\\Flagged', '\\HasNoChildren'), '/', u'[Gmail]/Starred'),
         (('\\HasNoChildren', '\\Trash'), '/', u'[Gmail]/Trash'),
         (('\\HasNoChildren',), '/', u'reference')]
    check_missing_generic('spam', folder_base, localized_folder_names['spam'],
                          'gmail', constants, monkeypatch)


def test_imap_missing_spam(constants, monkeypatch):
    '''
    Same strategy as test_gmail_missing_spam, except with imap as a provider
    '''
    folder_base = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'SKIP'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'Drafts'),
         (('\\HasNoChildren', '\\Sent'), '/', u'Sent'),
         (('\\HasNoChildren', '\\Sent'), '/', u'Sent Items'),
         (('\\HasNoChildren', '\\Trash'), '/', u'Trash'),
         (('\\HasNoChildren',), '/', u'reference')]
    check_missing_generic('spam', folder_base, localized_folder_names['spam'],
                          'imap', constants, monkeypatch)


def test_gmail_missing_sent(constants, monkeypatch):
    '''
    Same strategy as test_gmail_missing_trash, except with sent folder aliases
    '''
    # Create a list of folders thath doesn't have a sent folder
    folder_base = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'[Gmail]'),
         (('\\HasNoChildren', '\\All'), '/', u'[Gmail]/All Mail'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'[Gmail]/Drafts'),
         (('\\HasNoChildren', '\\Important'), '/', u'[Gmail]/Important'),
         (('\\HasNoChildren', '\\Junk'), '/', u'[Gmail]/Spam'),
         (('\\Flagged', '\\HasNoChildren'), '/', u'[Gmail]/Starred'),
         (('\\HasNoChildren', '\\Trash'), '/', u'[Gmail]/Trash'),
         (('\\HasNoChildren',), '/', u'reference')]
    check_missing_generic('sent', folder_base, localized_folder_names['sent'],
                          'gmail', constants, monkeypatch)


def test_imap_missing_sent(constants, monkeypatch):
    '''
    Almost same strategy as test_gmail_missing_sent,
    except with imap as a provider
    we can't really make call to checking_missing_geneirc,
    because imap and sent are
    special because there are allowed to be more than 1 sent folder.
    '''
    folder_base = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'SKIP'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'Drafts'),
         (('\\HasNoChildren', '\\Junk'), '/', u'Spam'),
         (('\\HasNoChildren', '\\Trash'), '/', u'Trash'),
         (('\\HasNoChildren',), '/', u'reference')]
    role_map = {
        'INBOX': 'inbox',
        'Trash': 'trash',
        'Drafts': 'drafts',
        'Spam': 'spam',
        u'reference': None
    }
    for role_alias in localized_folder_names['sent']:
        folders = folder_base + [(('\\HasNoChildren'), '/', role_alias)]
        client = patch_generic_client(monkeypatch, folders)
        raw_folders = client.folders()
        folder_names = client.folder_names()
        role_map[role_alias] = 'sent'

        # Explcit checks. Different than check_missing_generic
        # and generic_folder_checks, because imap allows
        # for 2 sent folders, and I couldn't quite make the check
        # be happy with only being given one sent folder alias
        for f in raw_folders:
            if f.display_name in role_map:
                assert f.role == role_map[f.display_name]
            else:
                assert f.display_name in ['reference']
                assert f.role is None
        for role in ['inbox', 'trash', 'drafts', 'sent', 'spam']:
            assert role in folder_names

            names = folder_names[role]
            assert isinstance(names, list)
            assert len(names) == 1

        del role_map[role_alias]


def check_missing_generic(role, folder_base, generic_role_names,
                          provider, constants, monkeypatch):
    '''
    check clients label every folder in generic_role_names as input role

    role: the role that the generic_role_names should be assigned
    folder_base: generic list of folders, excluding one that is assigned role
    generic_role_names: list of strings that represent common role liases for
    '''
    assert folder_base is not None
    role_map = constants['gmail_role_map'] \
               if provider == 'gmail' else constants['imap_role_map']
    # role_map is close, but not quite right, because it has a role key
    keys_to_remove = []
    # done in two loops to avoid modifying map while iterating through it
    for folder_name in role_map:
        if role_map[folder_name] == role:
            keys_to_remove.append(folder_name)
    for key in keys_to_remove:
        del role_map[key]
    for role_alias in generic_role_names:
        # add in a folder with name of role alias, without it's role flag
        folders = folder_base + [(('\\HasNoChildren'), '/', role_alias)]
        client = patch_gmail_client(monkeypatch, folders) \
                 if provider == 'gmail' \
                    else patch_generic_client(monkeypatch, folders)

        raw_folders = client.folders()
        role_map[role_alias] = role
        generic_folder_checks(raw_folders, role_map, client, provider)
        del role_map[role_alias]


def test_gmail_folders_no_flags(monkeypatch):
    """
    Tests that system folders (trash, inbox, sent) without flags can be labeled
    """

    folders = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'[Gmail]'),
         (('\\HasNoChildren', '\\All'), '/', u'[Gmail]/All Mail'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'[Gmail]/Drafts'),
         (('\\HasNoChildren', '\\Important'), '/', u'[Gmail]/Important'),
         (('\\HasNoChildren'), '/', u'[Gmail]/Sent Mail'),
         (('\\HasNoChildren'), '/', u'[Gmail]/Spam'),
         (('\\Flagged', '\\HasNoChildren'), '/', u'[Gmail]/Starred'),
         (('\\HasNoChildren'), '/', u'[Gmail]/Trash'),
         (('\\HasNoChildren',), '/', u'reference')]

    gmail_role_map = {
        '[Gmail]/All Mail': 'all',
        'Inbox': 'inbox',
        '[Gmail]/Trash': 'trash',
        '[Gmail]/Spam': 'spam',
        '[Gmail]/Drafts': 'drafts',
        '[Gmail]/Sent Mail': 'sent',
        '[Gmail]/Important': 'important',
        '[Gmail]/Starred': 'starred',
        'reference': None
    }
    client = patch_gmail_client(monkeypatch, folders)

    raw_folders = client.folders()
    generic_folder_checks(raw_folders, gmail_role_map, client, 'gmail')


def test_gmail_many_folders_one_role(monkeypatch, constants):
    """
    Tests that accounts with many folders with
    similar system folders have only one role.

    i.e accounts with [Imap]/Trash, Trash, and [Gmail]/Trash
    should only have one folder with the role trash
    """

    # some duplitace folders where one has been flagged,
    # and neither have been flagged
    # in both cases, only one should come out flagged.
    folders = constants['gmail_folders']
    duplicates = [(('\HasNoChildren'), '/', u'[Imap]/Trash'),
                  (('\\HasNoChildren'), '/', u'[Imap]/Sent')]
    folders += duplicates
    # This test adds [Imap]/Trash and [Imap]/sent
    # because we've seen them in the wild with gmail
    client = patch_gmail_client(monkeypatch, folders)

    raw_folders = client.folders()

    folder_names = client.folder_names()
    for role in ['inbox', 'all', 'trash', 'drafts', 'important', 'sent',
                 'spam', 'starred']:
        assert role in folder_names
        test_set = filter(lambda x: x == role,
                          map(lambda y: y.role, raw_folders))
        assert len(test_set) == 1, "assigned wrong number of {}".format(role)

        names = folder_names[role]
        assert isinstance(names, list)
        assert len(names) == 1, "assign same role to %s folders" % len(names)


def test_imap_folders(monkeypatch, constants):
    folders = constants['imap_folders']
    role_map = constants['imap_role_map']

    client = patch_generic_client(monkeypatch, folders)

    raw_folders = client.folders()
    generic_folder_checks(raw_folders, role_map, client, 'imap')


def test_imap_folders_no_flags(monkeypatch, constants):
    """
    Tests that system folders (trash, inbox, sent) without flags can be labeled
    """
    folders = \
        [(('\\HasNoChildren',), '/', u'INBOX'),
         (('\\Noselect', '\\HasChildren'), '/', u'SKIP'),
         (('\\HasNoChildren', '\\Drafts'), '/', u'Drafts'),
         (('\\HasNoChildren'), '/', u'Sent'),
         (('\\HasNoChildren'), '/', u'Sent Items'),
         (('\\HasNoChildren', '\\Junk'), '/', u'Spam'),
         (('\\HasNoChildren'), '/', u'Trash'),
         (('\\HasNoChildren',), '/', u'reference')]

    role_map = {
        'INBOX': 'inbox',
        'Trash': 'trash',
        'Drafts': 'drafts',
        'Sent': 'sent',
        'Sent Items': 'sent',
        'Spam': 'spam',
        u'[Gmail]/Sent Mail': None,
        u'[Gmail]/Trash': 'trash',
        u'reference': None
    }
    client = patch_generic_client(monkeypatch, folders)

    raw_folders = client.folders()
    generic_folder_checks(raw_folders, role_map, client, 'imap')


def test_imap_many_folders_one_role(monkeypatch, constants):
    """
    Tests that accounts with many folders with
    similar system folders have only one role.

    i.e accounts with [Imap]/Trash, Trash, and [Gmail]/Trash
    should only have one folder with the role trash

    This test should result in 2 sent folders, and 2 trash folders. There is an
    extra folder with the name sent, but since it doesn't have flags
    and there is already sent folder, than we don't coerce it to a sent folder
    """
    folders = constants['imap_folders']
    duplicates = [(('\HasNoChildren', '\\Trash'), '/', u'[Gmail]/Trash'),
                  (('\\HasNoChildren'), '/', u'[Gmail]/Sent')]
    folders += duplicates

    client = patch_generic_client(monkeypatch, folders)

    raw_folders = client.folders()
    folder_names = client.folder_names()
    for role in ['inbox', 'trash', 'drafts', 'sent', 'spam']:
        assert role in folder_names
        number_roles = 2 if (role in ['sent', 'trash']) else 1
        test_set = filter(lambda x: x == role,
                          map(lambda y: y.role, raw_folders))
        assert len(test_set) == number_roles,\
            "assigned wrong number of {}".format(role)
