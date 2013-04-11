import re
import cgi
from bs4 import BeautifulSoup

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



def trim_quoted_text(msg_text, content_type):

    if len(msg_text) == 0:
        log.error('No message recovered. Content-Type: %s'  % content_type)
        return

    # TODO add signature detection
    #  r'^-{2}\s' or something

    # TOFIX do this with from address?
    if content_type == "text/plain":
        regexes =  [r'-+original\s+message-+\s*$', 
                    r'^.*On\ .*(\n|\r|\r\n)?wrote:(\r)*$',
                    r'From:\s*' + re.escape(from_addr),
                    r'<' + re.escape(from_addr) + r'>',
                    re.escape(from_addr) + r'\s+wrote:',
                    r'from:\s*$']

    elif content_type == "text/html":
        regexes =  [r'-+original\s+message-+\s*', 
                    r'^.*On\ .*(\n|\r|\r\n)?wrote:(\r)*$',
                    r'<div class="gmail_quote">',
                    ]
                    # r'On\ .*(\n|\r|\r\n)?wrote:(\r)*']
    else :
        log.error('Not sure how to trim quoted text from Content-Type: ' + str(content_type))
        return

    endpoint = len(msg_text) # long email

    for r in regexes:
        m = re.search(r, msg_text, re.IGNORECASE | re.MULTILINE)
        if m == None: continue
        e = m.start()
        if m.start() < endpoint :
            endpoint = e

    msg_text = msg_text[: endpoint]

    # TODO this whitespace trimming should be part of regex
    while msg_text.endswith('\n') or msg_text.endswith('\r'):
        msg_text = msg_text[:-2]
        

    return msg_text


from urllib import urlencode
from hashlib import md5

def gravatar_url(email):

    default = "http://www.example.com/default.jpg"
    size = 25

    # construct the url
    gravatar_url = "http://www.gravatar.com/avatar/" + md5(email.lower()).hexdigest() + "?"
    gravatar_url += urlencode({'d':'mm', 's':str(size)})

    return gravatar_url

