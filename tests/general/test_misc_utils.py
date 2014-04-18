""" Tests for miscellaneous utility functions. """

from inbox.util.file import human_readable_filesize


def test_human_readable_filesize():
    """ Test that conversions match Google (e.g. "<num> bytes in <unit>".) """

    size_bytes = 10000000000
    result = human_readable_filesize(size_bytes)
    assert result == '9.31 GB'

    size_bytes = 100000000
    result = human_readable_filesize(size_bytes)
    assert result == '95.4 MB'

    size_bytes = 101324
    result = human_readable_filesize(size_bytes)
    assert result == '99 KB'
