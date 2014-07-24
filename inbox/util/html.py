import re
import cgi

from talon.quotations import (register_xpath_extensions, extract_from_html,
                              extract_from_plain)
register_xpath_extensions()

from HTMLParser import HTMLParser


# http://stackoverflow.com/questions/753052/strip-html-from-strings-in-python
class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return u''.join(self.fed)


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

# https://djangosnippets.org/snippets/19/
re_string = re.compile(ur'(?P<htmlchars>[<&>])|(?P<space>^[ \t]+)|(?P<lineend>\n)|(?P<protocol>(^|\s)((http|ftp)://.*?))(\s|$)', re.S|re.M|re.I|re.U)


def plaintext2html(text, tabstop=4):
    assert '\r' not in text, "newlines not normalized"

    def do_sub(m):
        c = m.groupdict()
        if c['htmlchars']:
            return cgi.escape(c['htmlchars'])
        if c['lineend']:
            return '<br>'
        elif c['space']:
            t = m.group().replace('\t', u'&nbsp;'*tabstop)
            t = t.replace(' ', '&nbsp;')
            return t
        elif c['space'] == '\t':
            return ' '*tabstop
        else:
            url = m.group('protocol')
            if url.startswith(' '):
                prefix = ' '
                url = url[1:]
            else:
                prefix = ''
            last = m.groups()[-1]
            if last in ['\n', '\r', '\r\n']:
                last = '<br>'
            return u'{0}<a href="{1}">{2}</a>{3}'.format(
                prefix, url, url, last)
    return '\n'.join([u'<p>{0}</p>'.format(
        re.sub(re_string, do_sub, p)) for p in text.split('\n\n')])


def common_intervals(an, bn):
    """
    finds intervals of common substrings given two strings
    """
    MIN_LEN = 7
    a = an.split()
    b = bn.split()

    def lcs(idx_a, idx_b):
        i = 0
        while idx_a + i < len(a) and idx_b + i < len(b) \
                and a[idx_a + i] == b[idx_b + i]:
            i += 1
        return i

    spans = []
    start_a, start_b = 0, 0

    while start_a < len(a) - MIN_LEN:
        while start_b < len(b) - MIN_LEN:
            l = lcs(start_a, start_b)
            if l >= MIN_LEN:
                spans.append((l, start_a, start_b))
            if l > 0:
                start_a += l
                start_b += l
            else:
                start_b += 1
        start_a += 1
        start_b = 0

    return spans
