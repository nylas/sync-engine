# -*- coding: utf-8 -*-
import re
import cgi
import htmlentitydefs
from HTMLParser import HTMLParser, HTMLParseError

from inbox.log import get_logger


# http://stackoverflow.com/questions/753052/strip-html-from-strings-in-python
class HTMLTagStripper(HTMLParser):
    strippedTags = ["title", "script", "style"]

    def __init__(self):
        self.reset()
        self.fed = []
        self.strip_tag_contents_mode = False

    def handle_starttag(self, tag, attrs):
        # Strip the contents of a tag when it's
        # in strippedTags. We can do this because
        # HTMLParser won't try to parse the inner
        # contents of a tag.
        if tag.lower() in HTMLTagStripper.strippedTags:
            self.strip_tag_contents_mode = True

    def handle_endtag(self, tag):
        self.strip_tag_contents_mode = False

    def handle_data(self, d):
        if not self.strip_tag_contents_mode:
            self.fed.append(d)

    def handle_charref(self, d):
        try:
            if d.startswith('x'):
                val = int(d[1:], 16)
            else:
                val = int(d)
        except ValueError:
            return
        self.fed.append(unichr(val))

    def handle_entityref(self, d):
        try:
            val = unichr(htmlentitydefs.name2codepoint[d])
        except KeyError:
            return
        self.fed.append(val)

    def get_data(self):
        return u''.join(self.fed)


def strip_tags(html):
    s = HTMLTagStripper()
    try:
        s.feed(html)
    except HTMLParseError:
        get_logger().error('error stripping tags', raw_html=html)
    return s.get_data()

# https://djangosnippets.org/snippets/19/
re_string = re.compile(ur'(?P<htmlchars>[<&>])|(?P<space>^[ \t]+)|(?P<lineend>\n)|(?P<protocol>(^|\s)((http|ftp)://.*?))(\s|$)', re.S|re.M|re.I|re.U)  # noqa


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
