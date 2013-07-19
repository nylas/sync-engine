from email.header import decode_header


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



def decode_data(data, data_encoding):
    data_encoding = data_encoding.lower()

    try:
        if data_encoding == 'quoted-printable':
            data = quopri.decodestring(data)
        elif data_encoding == '7bit':
            pass  # This is just ASCII. Do nothing.
        elif encoding.lower() == '8bit':
            pass  # .decode('8bit') does nothing.
        elif data_encoding == 'base64':
            data = data.decode('base-64')
        else:
            log.error("Unknown encoding scheme:" + str(encoding))
    except Exception, e:
        print 'Encoding not provided...'

    return data
