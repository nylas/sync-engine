

import re
import cgi

# Helpers

re_string = re.compile(r'(?P<htmlchars>[<&>])|(?P<space>^[ \t]+)|(?P<lineend>\r\n|\r|\n)|(?P<protocal>(^|\s)((http|ftp)://.*?))(\s|$)', re.S|re.M|re.I)
def plaintext2html(text, tabstop=4):
    def do_sub(m):
        c = m.groupdict()
        if c['htmlchars']:
            return cgi.escape(c['htmlchars'])
        if c['lineend']:
            return '<br/>'
        elif c['space']:
            t = m.group().replace('\t', '&nbsp;'*tabstop)
            t = t.replace(' ', '&nbsp;')
            return t
        elif c['space'] == '\t':
            return ' '*tabstop;
        else:
            url = m.group('protocal')
            if url.startswith(' '):
                prefix = ' '
                url = url[1:]
            else:
                prefix = ''
            last = m.groups()[-1]
            if last in ['\n', '\r', '\r\n']:
                last = '<br/>'
            return '%s<a href="%s">%s</a>%s' % (prefix, url, url, last)
    return re.sub(re_string, do_sub, text)


def fix_links(text):
    soup = BeautifulSoup(text)
    for a in soup.findAll('a'):
        a['target'] = "_blank"

    for b in soup.findAll('body'):
        new_tag = soup.new_tag('div')
        new_tag.contents = b.contents
        b.replace_with(new_tag)
    return str(soup)



from urllib import urlencode
from hashlib import md5

def gravatar_url(email):

    default = "http://www.example.com/default.jpg"
    size = 25

    # construct the url
    gravatar_url = "http://www.gravatar.com/avatar/" + md5(email.lower()).hexdigest() + "?"
    gravatar_url += urlencode({'d':'mm', 's':str(size)})

    return gravatar_url

