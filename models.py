

import logging as log

from webify import trim_subject, gravatar_url

# { 
# tos: [ <Contacts>, ... ]
# from: 
#     [ <Contact> name, address, ... ]
# headers:
#     { 'someheader', value}

# body-text { 'content-type', bodyvalue}
#     >>> somehow have resource keys in body-text

# resources {'file-key', value}

# }



class Message():
    def __init__(self):
        self.to_contacts = []
        self.from_contacts = None
        self.subject = None

        self.date = None
        self.body_text = {}

        self.thread_id = None
        self.size = None
        self.uid = None

    def gravatar(self):
        return gravatar_url(self.from_contacts[0]['address'])

    def gmail_url(self):
        if not self.uid:
            return
        return "https://mail.google.com/mail/u/0/#inbox/" + hex(self.uid)

    def trimmed_subject(self):
        return trim_subject(self.subject)


class MessageThread():
    def __init__(self):
        self.messages = []
        self.thread_id = None
        self.is_unread = True # True/False

    @property
    def message_count(self):
        return len(self.messages)

    @property
    def subject(self):
        return self.messages[0].subject

    @property
    def most_recent_date(self):
        dates = [m.date for m in self.messages]
        dates.sort()
        return dates[-1]

    @property
    def datestring(self):
        return self.most_recent_date.strftime('%b %d, %Y &mdash; %I:%M %p')



## MessageBodyPart (BODYSTRUCTURE)

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


class MessageBodyPart(object):
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
        self.bytes = 0 # number of octets.

        # for text
        self.line_count = 0
        self.charset = ''
        self.encoding = ''

        # for images
        self.filename = ''



        self.index = str(index)
        self.content_type_major = p[0]
        self.content_type_minor = p[1]

        if self.content_type_major.lower() == 'text':
            assert p[2][0].lower() == 'charset'
            assert len(p) == 8 # TOFIX ?
            self.charset = p[2][1]
            self.encoding = p[5]
            self.bytes = p[6]
            self.line_count = p[7]

        elif self.content_type_major.lower() == 'image':
            assert p[2][0].lower() == 'name'
            assert len(p) == 7 # TOFIX ?
            self.filename = p[2][1]
            self.encoding = p[5]
            self.bytes = p[6]
        else:
            # Other random body section types here:
            # ('APPLICATION', 'PKCS7-SIGNATURE', ('NAME', 'smime.p7s'), None, None, 'BASE64', 2176)

            log.error('No idea what to do with this BODYSTRUCTURE: %s', p)


    @property
    def isImage(self):
        return self.content_type_major.lower() == 'image'

    def __repr__(self):
        r = '<MessageBodyPart object> '
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



