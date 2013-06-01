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


# Makes links have target='_blank'


def fix_links(text):

    # This is based on Tornado's built-in linkify function but it
    # doesn't escape everything first.
    _URL_RE = re.compile(ur"""\b((?:([\w-]+):(/{1,3})|www[.])(?:(?:(?:[^\s&()]|&amp;|&quot;)*(?:[^!"#$%&'()*+,.:;<=>?@\[\]^`{|}~\s]))|(?:\((?:[^\s&()]|&amp;|&quot;)*\)))+)""")
    permitted_protocols=["http", "https"]
    require_protocol = False
    shorten = True

    def make_link(m):
        url = m.group(1)
        proto = m.group(2)
        if require_protocol and not proto:
            return url  # not protocol, no linkify

        if proto and proto not in permitted_protocols:
            return url  # bad protocol, no linkify

        href = m.group(1)
        if not proto:
            href = "http://" + href   # no proto specified, use http

        params = ''

        # clip long urls. max_len is just an approximation
        max_len = 30
        if shorten and len(url) > max_len:
            before_clip = url
            if proto:
                proto_len = len(proto) + 1 + len(m.group(3) or "")  # +1 for :
            else:
                proto_len = 0

            parts = url[proto_len:].split("/")
            if len(parts) > 1:
                # Grab the whole host part plus the first bit of the path
                # The path is usually not that interesting once shortened
                # (no more slug, etc), so it really just provides a little
                # extra indication of shortening.
                url = url[:proto_len] + parts[0] + "/" + \
                        parts[1][:8].split('?')[0].split('.')[0]

            if len(url) > max_len * 1.5:  # still too long
                url = url[:max_len]

            if url != before_clip:
                amp = url.rfind('&')
                # avoid splitting html char entities
                if amp > max_len - 5:
                    url = url[:amp]
                url += "..."

                if len(url) >= len(before_clip):
                    url = before_clip
                else:
                    # full url is visible on mouse-over (for those who don't
                    # have a status bar, such as Safari by default)
                    params += ' title="%s"' % href

        return u'<a target="_blank" href="%s"%s>%s</a>' % (href, params, url)

    # First HTML-escape so that our strings are all safe.
    # The regex is modified to avoid character entites other than &amp; so
    # that we won't pick up &quot;, etc.
    # text = _unicode(xhtml_escape(text))


    text =  _URL_RE.sub(make_link, text)

    return text


    # import re
    # urlfinder = re.compile("([0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}|((news|telnet|nttp|file|http|ftp|https)://)|(www|ftp)[-A-Za-z0-9]*\\.)[-A-Za-z0-9\\.]+):[0-9]*)?/[-A-Za-z0-9_\\$\\.\\+\\!\\*\\(\\),;:@&=\\?/~\\#\\%]*[^]'\\.}>\\),\\\"]")
    # text = urlfinder.sub(r'<a href="\1">\1</a>', text)

    # soup = BeautifulSoup(text)
    # for a in soup.findAll('a'):
    #     a['target'] = "_blank"

    # for b in soup.findAll('body'):
    #     new_tag = soup.new_tag('div')
    #     new_tag.contents = b.contents
    #     b.replace_with(new_tag)
    # return str(soup)



def trim_quoted_text(msg_text, content_type):

    if len(msg_text) == 0:
        log.error('No message recovered. Content-Type: %s'  % content_type)
        return

    # TODO add signature detection
    #  r'^-{2}\s' or something

    # TOFIX do this with from address?
    if content_type == "text/plain":
        # regexes =  [r'-+original\s+message-+\s*$', 
        #             r'^.*On\ .*(\n|\r|\r\n)?wrote:(\r)*$',
        #             r'From:\s*' + re.escape(from_addr),
        #             r'<' + re.escape(from_addr) + r'>',
        #             re.escape(from_addr) + r'\s+wrote:',
        #             r'from:\s*$']

        regexes =  [r'from:\s*$',
                    r'-+original\s+message-+\s*$', 
                    r'^.*On\ .*(\n|\r|\r\n)?wrote:(\r)*$',
                    r'\s+wrote:$',
                    ]

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

