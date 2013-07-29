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

        self.to_contacts = None
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



class IBMessagePart(object):
    """The parts of message's body content"""

    def __init__(self):
        self.index = None
        self.content_type_major = None
        self.content_type_minor = None

        self.charset = None
        self.encoding = None
        self.bytes = None  # number of octets TODO is this encoded (transfer)?
        self.line_count = None
        self.filename = None


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
        return '<IBMessagePart object> %s' % self.toJSON()


