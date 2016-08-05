from inbox.models.message import _trim_filename


def test_filename_truncation():
    # Note: test both 3-byte and 4-byte UTF8 chars to make sure truncation
    # follows UTF8 boundaries.
    uname = u'\U0001f1fa\U0001f1f8\u2678\U0001f602.txt'
    assert _trim_filename(uname, 'a', max_len=8) == uname
    assert _trim_filename(uname, 'a', max_len=7) == u'\U0001f1fa\U0001f1f8\u2678.txt'
    assert _trim_filename(uname, 'a', max_len=6) == u'\U0001f1fa\U0001f1f8.txt'
    assert _trim_filename(uname, 'a', max_len=5) == u'\U0001f1fa.txt'

    # Note: Test input that is not unicode, ensure it uses unicode length not byte length
    cname = '\xf0\x9f\x87\xba\xf0\x9f\x87\xb8\xe2\x99\xb8\xf0\x9f\x98\x82.txt'
    assert _trim_filename(cname, 'a', max_len=8) == uname
    assert _trim_filename(cname, 'a', max_len=7) == u'\U0001f1fa\U0001f1f8\u2678.txt'
    assert _trim_filename(cname, 'a', max_len=6) == u'\U0001f1fa\U0001f1f8.txt'
    assert _trim_filename(cname, 'a', max_len=5) == u'\U0001f1fa.txt'
