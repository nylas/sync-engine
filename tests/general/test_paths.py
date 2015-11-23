# Test path conversion functions.
from inbox.util.misc import imap_folder_path, fs_folder_path, is_imap_folder_path


def test_imap_folder_path():
    assert imap_folder_path('/a/b') == 'INBOX.a.b'
    assert imap_folder_path('/A/b') == 'INBOX.A.b'
    assert imap_folder_path('/a/very/deep/nested/folder') == 'INBOX.a.very.deep.nested.folder'
    assert imap_folder_path('') == 'INBOX'


def test_fs_folder_path():
    assert fs_folder_path('INBOX.A.B') == 'A/B'
    assert fs_folder_path('INBOX.a.very.deep.nested.folder') == 'a/very/deep/nested/folder'
    assert fs_folder_path(imap_folder_path('/a/b')) == 'a/b'


def test_is_imap_folder_path():
    assert is_imap_folder_path('INBOX.A.B') == True
    assert is_imap_folder_path('INBOX.A') == True
    assert is_imap_folder_path('INBOX') == False
    assert is_imap_folder_path('INBOX/B') == True
    assert is_imap_folder_path('A/B') == False
