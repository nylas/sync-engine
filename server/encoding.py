from email.header import decode_header
import quopri
from bs4 import BeautifulSoup
import re
import cgi
import bleach
import logging as log


def make_unicode(txt, default_encoding="ascii"):
    try:
        return u"".join([unicode(text, charset or default_encoding, 'strict')
                for text, charset in decode_header(txt)])
    except Exception, e:
        log.error("Problem converting string to unicode: %s" % txt)
        return u"".join([unicode(text, charset or default_encoding, 'replace')
                for text, charset in decode_header(txt)])

# Older version

# def clean_header(to_decode):
#     from email.header import decode_header
#     decoded = decode_header(to_decode)
#     parts = [w.decode(e or 'ascii') for w,e in decoded]
#     u = u' '.join(parts)
#     return u




# TODO Some notes about base64 downloading:

# Some b64 messages may have other additonal encodings
# Some example strings:

#     '=?Windows-1251?B?ICLRLcvu5Obo8fLo6iI?=',
#     '=?koi8-r?B?5tLPzM/XwSDtwdLJzsEg98nUwczYxdfOwQ?=',
#     '=?Windows-1251?B?1PDu6+7i4CDM4PDo7eAgwujy4Ov85eLt4A?='

# In these situations, we should split by '?' and then grab the encoding

# def decodeStr(s):
#     s = s.split('?')
#     enc = s[1]
#     dat = s[3]
#     return (dat+'===').decode('base-64').decode(enc)

# The reason for the '===' is that base64 works by regrouping bits; it turns
# 3 8-bit chars into 4 6-bit chars (then refills the empty top bits with 0s).
# To reverse this, it expects 4 chars at a time - the length of your string
# must be a multiple of 4 characters. The '=' chars are recognized as padding;
# three chars of padding is enough to make any string a multiple of 4 chars long


import base64


def decode_data(data, data_encoding):
    data_encoding = data_encoding.lower()

    try:
        if data_encoding == 'quoted-printable':
            data = quopri.decodestring(data)
        elif data_encoding == '7bit':
            pass  # This is just ASCII. Do nothing.
        elif data_encoding == '8bit':
            pass  # .decode('8bit') does nothing.
        elif data_encoding == 'base64':
            # data = data.decode('base-64')
            data = base64.b64decode(data)
        else:
            log.error("Unknown encoding scheme:" + str(encoding))
    except Exception, e:
        print 'Encoding not provided: %s' % e

    return data


import chardet

def decode_part(data, part):
    data_encoding = part.encoding.lower()

    if data_encoding == 'quoted-printable':
        data = quopri.decodestring(data)

        charset = part.charset
        if not charset:
            result = chardet.detect(data)
            log.info("Detected charset %s with confidence %s" % ( result['encoding'], str(result['confidence']) ) )
            charset = result['encoding']

        if not isinstance(data, unicode):
            data = unicode(data, charset or "ascii", 'strict')

    elif data_encoding == '7bit':
        pass  # This is just ASCII. Do nothing.
    elif data_encoding == '8bit':
        pass  # .decode('8bit') does nothing.
    elif data_encoding == 'base64':
        # data = data.decode('base-64')
        data = base64.b64decode(data)
    else:
        log.error("Unknown encoding scheme:" + str(encoding))
        raise Exception("No encoding type recognized")

    return data






def clean_html(msg_data):
    """ Removes tags: head, style, script, html, body """

    soup = BeautifulSoup(msg_data)

    [tag.extract() for tag in soup.findAll(["script", "head", "style", "meta", "link"])]

    for m in soup('html'): m.replaceWithChildren()
    for m in soup('body'): m.replaceWithChildren()


    # for match in soup.findAll('body'):
    #     print 'MATCHED!'
    #     match.replaceWithChildren()
    #     # new_tag = soup.new_tag('div')
    #     # new_tag.contents = b.contents
    #     # b.replace_with(new_tag)
    return str(soup)



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





# TODO this doesn't work.

def trim_quoted_text(msg_text, content_type):
    """ Given the text of a message, this separates the
        main content from the quoted messages
    """

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





