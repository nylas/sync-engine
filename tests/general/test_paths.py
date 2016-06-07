# Test path conversion functions.
from inbox.util.misc import imap_folder_path, fs_folder_path


def test_imap_folder_path():
    assert imap_folder_path('a/b') == 'a.b'
    assert imap_folder_path('a/b', separator='?') == 'a?b'

    assert imap_folder_path('/A/b') == 'A.b'
    assert imap_folder_path('/INBOX/b') == 'INBOX.b'
    assert imap_folder_path('INBOX/b') == 'INBOX.b'

    assert imap_folder_path('a/very/deep/nested/folder') == 'a.very.deep.nested.folder'
    assert imap_folder_path('/a/very/deep/nested/folder') == 'a.very.deep.nested.folder'

    assert imap_folder_path('') is None
    assert imap_folder_path('/') is None

    assert imap_folder_path('A/B', prefix='INBOX.', separator='.') == 'INBOX.A.B'
    assert imap_folder_path('/A/B', prefix='INBOX.', separator='.') == 'INBOX.A.B'
    assert imap_folder_path('/A/B', prefix='INBOX', separator='.') == 'INBOX.A.B'
    assert imap_folder_path('INBOX/A/B', prefix='INBOX', separator='.') == 'INBOX.A.B'


def test_fs_folder_path():
    assert fs_folder_path('INBOX.A.B') == 'INBOX/A/B'
    assert fs_folder_path('INBOX.A.B', prefix='INBOX.') == 'A/B'
    assert fs_folder_path('INBOX?A?B', prefix='INBOX?', separator='?') == 'A/B'
    assert fs_folder_path('INBOX.a.very.deep.nested.folder') == 'INBOX/a/very/deep/nested/folder'
    assert fs_folder_path(imap_folder_path('a/b')) == 'a/b'
