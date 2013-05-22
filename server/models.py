import logging as log
import json
import email.utils as email_utils
from email.header import decode_header
import time
import datetime


class IBContact():
    def __init__(self):
        self.firstname = ""
        self.lastname = ""
        self.email = ""

    def gravatar(self):
        return gravatar_url(self.email)

    def toJSON(self):
        return dict( firstname = self.firstname,
                     lastname = self.lastname,
                     email = self.email)



class IBThread():
    def __init__(self):
        self.message_ids = []
        self.thread_id = None
        self.labels = []

    def __repr__(self):
        return '<IBThread object> ' +\
                '    thr_id: ' + str(self.thread_id) + \
                '    message_ids: ' + str(self.message_ids) + \
                '    labels: ' + str(self.labels)
                

    def toJSON(self):
        return dict( message_ids = [str(s) for s in self.message_ids],
                     thread_id = str(self.thread_id),
                     labels = [str(s) for s in self.labels]
                    )


class IBMessage():
    def __init__(self, email_message_object = None):
        self.message_id = "foo message id"
        self.thread_id = None
        self.size = None
        self.uid = None

        self.to_contacts = []
        self.from_contacts = None
        self.subject = None

        self.date = None
        self.message_parts = []  # list of indicies
        self.labels = []


        # Kickstart it using the headers from this object
        if (email_message_object):

            def make_uni(txt, default_encoding="ascii"):
                try:
                    return u"".join([unicode(text, charset or default_encoding, 'strict')
                            for text, charset in decode_header(txt)])
                except Exception, e:
                    log.error("Problem converting string to unicode: %s" % txt)
                    return u"".join([unicode(text, charset or default_encoding, 'replace')
                            for text, charset in decode_header(txt)])

            def parse_contact(headers):
                # Works with both strings and lists
                try: headers += []
                except: headers = [headers]

                # combine and flatten header values
                addrs = reduce(lambda x,y: x+y, [email_message_object.get_all(a, []) for a in headers])

                if len(addrs) > 0:
                    return [ dict(name = make_uni(t[0]),
                                address=make_uni(t[1]))
                            for t in email_utils.getaddresses(addrs)]
                else:
                    return [ dict(name = "undisclosed recipients", address = "") ]

            self.to_contacts = parse_contact(['to', 'cc'])
            self.from_contacts = parse_contact(['from'])

            self.message_id = email_message_object['X-GM-MSGID']
            self.thread_id = email_message_object['X-GM-THRID']

            subject = make_uni(email_message_object['subject'])
            # Need to trim the subject.
            # Headers will wrap when longer than 78 lines per RFC822_2
            subject = subject.replace('\n\t', '').replace('\r\n', '')
            self.subject = subject

            # TODO remove the subject headings here like RE: FWD: etc.
            #     # Remove "RE" or whatever
            #     if subject[:4] == u'RE: ' or subject[:4] == u'Re: ' :
            #         subject = subject[4:]
            #     return subject


            # TODO: Gmail's timezone is usually UTC-07:00
            # see here. We need to figure out how to deal with timezones.
            # http://stackoverflow.com/questions/11218727/what-timezone-does-gmail-use-for-internal-imap-mailstore
            # TODO: Also, we should reallly be using INTERNALDATE instead of ENVELOPE data
            date_tuple_with_tz = email_utils.parsedate_tz(email_message_object["Date"])
            utc_timestamp = email_utils.mktime_tz(date_tuple_with_tz)
            time_epoch = time.mktime( date_tuple_with_tz[:9] )
            self.date = datetime.datetime.fromtimestamp(utc_timestamp)



    def __repr__(self):
        return '<IBMessage object> ' + \
                '\n    msg_id: ' + str(self.message_id) +\
                '\n    thr_id: ' + str(self.thread_id) +\
                '\n    to: %s ' + str(self.to_contacts) +\
                '\n    from: %s' + str(self.from_contacts) +\
                '\n    subj: ' + str(self.subject) +\
                '\n    date epoch: ' + str( time.mktime(self.date.timetuple() )) +\
                '\n    with %d parts.\n' % len(self.message_parts)


    def gmail_url(self):
        if not self.uid:
            return
        return "https://mail.google.com/mail/u/0/#inbox/" + hex(self.uid)

    def trimmed_subject(self):
        return trim_subject(self.subject)

    def toJSON(self):
        return dict(
            to_contacts = self.to_contacts,
            from_contacts = self.from_contacts,
            subject = self.subject,
            date = str( time.mktime(self.date.timetuple() )), # since poch
            body_text =  "foo") # TODO Fix this


        # self.message_id = "foo message id"
        # self.thread_id = None
        # self.size = None
        # self.uid = None

        # self.to_contacts = []
        # self.from_contacts = None
        # self.subject = None

        # self.date = None
        # self.message_parts = []  # list of indicies
        # self.labels = []




# BODY is like BODYSTRUCTURE but without extension information
# not sure what this means in practice. We can probably get by only
# using BODY requests and just looking up the filetype based on filename 
# extensions. Excerpts from a couple of Gmail responses:

# snipped of BODY request of attachment
# ('IMAGE', 'JPEG', ('NAME', 'breadSRSLY-5.jpg'), None, None, 'BASE64', 1611294),

# snippet of BODYSTRUCTURE
# ('IMAGE', 'JPEG', ('NAME', 'breadSRSLY-5.jpg'), None, None, 'BASE64', 1611294, None, ('ATTACHMENT', ('FILENAME', 'breadSRSLY-5.jpg')), None), 

# From the original spec...
#
# A body type of type TEXT contains, immediately after the basic 
# fields, the size of the body in text lines.  Note that this 
# size is the size in its content transfer encoding and not the 
# resulting size after any decoding. 
#
# Extension data follows the basic fields and the type-specific 
# fields listed above.  Extension data is never returned with the 
# BODY fetch, but *CAN* be returned with a BODYSTRUCTURE fetch. 
# Extension data, if present, MUST be in the defined order. 
#
# Also, BODY and BODYSTRUCTURE calls are kind of fucked
# see here http://mailman2.u.washington.edu/pipermail/imap-protocol/2011-October/001528.html


# ([
#    ('text', 'html', ('charset', 'us-ascii'), None, None, 'quoted-printable', 55, 3),
#    ('text', 'plain', ('charset', 'us-ascii'), None, None, '7bit', 26, 1) 
#  ], 
#  'mixed', ('boundary', '===============1534046211=='))

# print 'Parts:', len(parts)
# $ UID FETCH <uid> (BODY ENVELOPE)   # get structure and header info
# $ UID FETCH <uid> (BODY[1])         # retrieving displayable body
# $ UID FETCH <uid> (BODY[2])         # retrieving attachment on demand
# FETCH 88 BODY.PEEK[1]
# FETCH uid BODY.PEEK[1.2]
# print 'Ending:', bodystructure[1]


class IBMessagePart(object):
    """The parts of message's body content"""
    def __init__(self, p, index='1'):
        """p is tuple returned by the BODYSTRUCTURE command"""

        self.index = "" # String describing body position, 1-indexed
        # this describes how to retreive the content
        # For parts at the top level, it will be something like "1"
        # such that a call to requets it is BODY[1]
        # For subparts, it follows the dot notation, so "1.1" is the 
        # first subpart of the first part, fetched with BODY[1.1]

        self.content_type_major = ''
        self.content_type_minor = ''

        # TODO check to see if this is the encoded or actual size
        self.bytes = 0  # number of octets.

        # for text
        self.line_count = 0
        self.charset = ''
        self.encoding = ''

        # for images
        self.filename = ''

        if len(p) == 0:
            return
        elif len(p) == 1:
            self.content_type_major = 'multipart'
            self.content_type_minor = p[0]
        elif len(p) == 2:
            self.content_type_major = p[0]
            self.content_type_minor = p[1]
        else:

            try:

                # instantiate
                self.index = str(index)
                self.content_type_major = p[0]
                self.content_type_minor = p[1]

                if self.content_type_major.lower() == 'text':
                    assert len(p) == 8  # TOFIX ?
                    if p[2]:  # charset
                        try:
                            assert p[2][0].lower() == 'charset'
                            self.charset = p[2][1]
                        except Exception, e:
                            # raise e
                            print 'What is here instead?', p[2]

                    self.encoding = p[5]
                    self.bytes = p[6]
                    self.line_count = p[7]

                elif self.content_type_major.lower() == 'image':
                    assert p[2][0].lower() == 'name'
                    assert len(p) == 7  # TOFIX ?
                    self.filename = p[2][1]
                    self.encoding = p[5]
                    self.bytes = p[6]
                else:
                    # Other random body section types here:
                    # ('APPLICATION', 'PKCS7-SIGNATURE', ('NAME', 'smime.p7s'), None, None, 'BASE64', 2176)

                    log.error('No idea what to do with this BODYSTRUCTURE: %s', p)

            except Exception, e:
                print 'Goddammit bug', e, p
                pass


    @property
    def isImage(self):
        return self.content_type_major.lower() == 'image'

    def __repr__(self):
        r = '<IBMessagePart object> '
        if self.content_type_major.lower() == 'text':
            return r + 'BodySection %s: %s text (%i bytes, %i lines) with encoding: %s' % \
                          (self.index, 
                           self.content_type_minor.lower(), 
                           self.bytes, 
                           self.line_count,
                           self.encoding)
        elif self.content_type_major.lower() == 'image':
            return r + 'BodySection %s: %s (%i byes) with Content-Type: %s/%s' % \
                           (self.index,
                            self.filename,
                            self.bytes, 
                            self.content_type_major.lower(), 
                            self.content_type_minor.lower() )
        else:
            return r + ''
