import logging as log
import json
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
        self.message_parts = []
        self.attachments = []
        self.signatures = []
        self.labels = []

        self.envelope = None   # TOFIX store this too?


    def gmail_url(self):
        if not self.uid:
            return
        return "https://mail.google.com/mail/u/0/#inbox/" + hex(self.uid)


    def trimmed_subject(self):
        s = self.subject
        if s[:4] == u'RE: ' or s[:4] == u'Re: ' :
            s = s[4:]
        return s


    @property
    def time_since_epoch(self):
        return time.mktime(self.date.timetuple()) if self.date else 0

    def toJSON(self):
        return dict(
            message_id = self.message_id,
            thread_id = self.thread_id,
            labels = self.labels,
            uid = self.uid,
            to_contacts = self.to_contacts,
            from_contacts = self.from_contacts,
            subject = self.subject,
            date = str(self.time_since_epoch), # since poch
            message_parts = [p.toJSON() for p in self.message_parts],
            attachments = [p.toJSON() for p in self.attachments],
            signatures = [p.toJSON() for p in self.signatures] )


    def __repr__(self):
        return 'IBMessage object: \n\t%s' % self.toJSON()


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
        # size in its content transfer encoding and not the resulting size after any decoding
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

                # just a regular file here
                else:
                    if p[2] and not isinstance(p[2], basestring):  # is there a filename?
                        assert p[2][0].lower() == 'name'
                        self.filename = p[2][1]
                    self.encoding = p[5]
                    self.bytes = p[6]

                    print 'file encoding:', self.encoding

            except Exception, e:
                print e, 'Unparsable mine type thing', p
                pass


    @property
    def isImage(self):
        return self.content_type_major.lower() == 'image'



    def toJSON(self):
        if self.content_type_major.lower() == 'text':
            return dict(
                content_type = "%s/%s" % (self.content_type_major, self.content_type_minor),
                bytes = self.bytes,
                index = self.index,
                encoding = self.encoding,
            )
        else:
            return dict(
                content_type = "%s/%s" % (self.content_type_major, self.content_type_minor),
                bytes = self.bytes,
                index = self.index,
                encoding = self.encoding,
                filename = self.filename
            )

    def __repr__(self):
        return '<IBMessagePart object> %s' % self.toJson()

