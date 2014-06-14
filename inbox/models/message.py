import os
import json
from hashlib import sha256
from flanker import mime

from sqlalchemy import (Column, Integer, BigInteger, String, DateTime,
                        Boolean, Enum, ForeignKey, Text)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql.expression import false

from inbox.util.html import (plaintext2html, strip_tags,
                             extract_from_html, extract_from_plain)
from inbox.sqlalchemy_ext.util import JSON

from inbox.config import config
from inbox.util.addr import parse_email_address_list
from inbox.util.file import mkdirp
from inbox.util.misc import parse_ml_headers, parse_references

from inbox.models.mixins import HasPublicID
from inbox.models.transaction import HasRevisions
from inbox.models.base import MailSyncBase


from inbox.log import get_logger
log = get_logger()


def _trim_filename(s, max_len=64, log=None):
    if s and len(s) > max_len:
        if log:
            log.warning(u"field is too long. Truncating to {}"
                        u"characters. {}".format(max_len, s))
        return s[:max_len - 8] + s[-8:]  # Keep extension
    return s


def _get_errfilename(account_id, folder_name, uid):
    errdir = os.path.join(config['LOGDIR'], str(account_id), 'errors',
                          folder_name)
    errfile = os.path.join(errdir, str(uid))
    mkdirp(errdir)
    return errfile


def _log_decode_error(account_id, folder_name, uid, msg_string):
    """ msg_string is in the original encoding pulled off the wire """
    errfile = _get_errfilename(account_id, folder_name, uid)
    with open(errfile, 'w') as fh:
        fh.write(msg_string)


class Message(MailSyncBase, HasRevisions, HasPublicID):
    # XXX clean this up a lot - make a better constructor, maybe taking
    # a flanker object as an argument to prefill a lot of attributes

    # Do delete messages if their associated thread is deleted.
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    thread = relationship(
        'Thread',
        primaryjoin='and_(Message.thread_id == Thread.id, '
                    'Thread.deleted_at.is_(None))',
        backref=backref('messages',
                        primaryjoin='and_('
                        'Message.thread_id == Thread.id, '
                        'Message.deleted_at.is_(None))',
                        order_by='Message.received_date',
                        info={'versioned_properties': ['id']}))

    from_addr = Column(JSON, nullable=True)
    sender_addr = Column(JSON, nullable=True)
    reply_to = Column(JSON, nullable=True)
    to_addr = Column(JSON, nullable=True)
    cc_addr = Column(JSON, nullable=True)
    bcc_addr = Column(JSON, nullable=True)
    in_reply_to = Column(JSON, nullable=True)
    message_id_header = Column(String(255), nullable=True)
    subject = Column(Text, nullable=True)
    received_date = Column(DateTime, nullable=False)
    size = Column(Integer, nullable=False)
    data_sha256 = Column(String(255), nullable=True)

    mailing_list_headers = Column(JSON, nullable=True)

    is_draft = Column(Boolean, server_default=false(), nullable=False)
    is_read = Column(Boolean, server_default=false(), nullable=False)

    # Most messages are short and include a lot of quoted text. Preprocessing
    # just the relevant part out makes a big difference in how much data we
    # need to send over the wire.
    # Maximum length is determined by typical email size limits (25 MB body +
    # attachments on Gmail), assuming a maximum # of chars determined by
    # 1-byte (ASCII) chars.
    # NOTE: always HTML :)
    sanitized_body = Column(Text(length=26214400), nullable=False)
    snippet = Column(String(191), nullable=False)
    SNIPPET_LENGTH = 191

    # we had to replace utf-8 errors before writing... this might be a
    # mail-parsing bug, or just a message from a bad client.
    decode_error = Column(Boolean, server_default=false(), nullable=False)

    # only on messages from Gmail
    g_msgid = Column(BigInteger, nullable=True, index=True)
    g_thrid = Column(BigInteger, nullable=True, index=True)

    # The uid as set in the X-INBOX-ID header of a sent message we create
    inbox_uid = Column(String(64), nullable=True)

    # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
    references = Column(JSON, nullable=True)

    @property
    def namespace(self):
        return self.thread.namespace

    def __init__(self, account=None, mid=None, folder_name=None,
                 received_date=None, flags=None, body_string=None,
                 *args, **kwargs):
        """ Parses message data and writes out db metadata and MIME blocks.

        Returns the new Message, which links to the new Block objects through
        relationships. All new objects are uncommitted.

        Threads are not computed here; you gotta do that separately.

        Parameters
        ----------
        mid : int
            The account backend-specific message identifier; it's only used for
            logging errors.

        raw_message : str
            The full message including headers (encoded).
        """

        _rqd = [account, mid, folder_name, received_date, flags, body_string]

        if not any(_rqd):
            MailSyncBase.__init__(self, *args, **kwargs)
            return

        if any(_rqd) and not all([v is not None for v in _rqd]):
            raise ValueError(
                "Required keyword arguments: account, mid, folder_name, "
                "received_date, flags, body_string")

        # trickle-down bugs
        assert account.namespace is not None
        assert not isinstance(body_string, unicode)

        try:
            parsed = mime.from_string(body_string)

            mime_version = parsed.headers.get('Mime-Version')
            # NOTE: sometimes MIME-Version is set to "1.0 (1.0)", hence the
            # .startswith
            if mime_version is not None and not mime_version.startswith('1.0'):
                log.error('Unexpected MIME-Version: {0}'.format(mime_version))

            self.data_sha256 = sha256(body_string).hexdigest()

            # clean_subject strips re:, fwd: etc.
            self.subject = parsed.clean_subject
            self.from_addr = parse_email_address_list(
                parsed.headers.get('From'))
            self.sender_addr = parse_email_address_list(
                parsed.headers.get('Sender'))
            self.reply_to = parse_email_address_list(
                parsed.headers.get('Reply-To'))

            self.to_addr = parse_email_address_list(
                parsed.headers.getall('To'))
            self.cc_addr = parse_email_address_list(
                parsed.headers.getall('Cc'))
            self.bcc_addr = parse_email_address_list(
                parsed.headers.getall('Bcc'))

            self.in_reply_to = parsed.headers.get('In-Reply-To')
            self.message_id_header = parsed.headers.get('Message-Id')

            self.received_date = received_date

            # Optional mailing list headers
            self.mailing_list_headers = parse_ml_headers(parsed.headers)

            # Custom Inbox header
            self.inbox_uid = parsed.headers.get('X-INBOX-ID')

            # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
            self.references = parse_references(
                parsed.headers.get('References', ''),
                parsed.headers.get('In-Reply-To', ''))

            self.size = len(body_string)  # includes headers text

            i = 0  # for walk_index

            from inbox.models.block import Part

            # Store all message headers as object with index 0
            headers_part = Part()
            headers_part.namespace_id = account.namespace.id
            headers_part.message = self
            headers_part.walk_index = i
            headers_part.data = json.dumps(parsed.headers.items())
            self.parts.append(headers_part)

            for mimepart in parsed.walk(
                    with_self=parsed.content_type.is_singlepart()):
                i += 1
                if mimepart.content_type.is_multipart():
                    log.warning("multipart sub-part found! on {}"
                                .format(self.g_msgid))
                    continue  # TODO should we store relations?

                new_part = Part()
                new_part.namespace_id = account.namespace.id
                new_part.message = self
                new_part.walk_index = i
                new_part.misc_keyval = mimepart.headers.items()  # everything
                new_part.content_type = mimepart.content_type.value
                new_part.filename = _trim_filename(
                    mimepart.content_type.params.get('name'),
                    log=log)
                # TODO maybe also trim other headers?

                if mimepart.content_disposition[0] is not None:
                    value, params = mimepart.content_disposition
                    if value not in ['inline', 'attachment']:
                        errmsg = """
        Unknown Content-Disposition on message {0} found in {1}.
        Bad Content-Disposition was: '{2}'
        Parsed Content-Disposition was: '{3}'""".format(
                            mid, folder_name, mimepart.content_disposition)
                        log.error(errmsg)
                        continue
                    else:
                        new_part.content_disposition = value
                        if value == 'attachment':
                            new_part.filename = _trim_filename(
                                params.get('filename'),
                                log=log)

                if mimepart.body is None:
                    data_to_write = ''
                elif new_part.content_type.startswith('text'):
                    data_to_write = mimepart.body.encode('utf-8', 'strict')
                    # normalize mac/win/unix newlines
                    data_to_write = data_to_write \
                        .replace('\r\n', '\n').replace('\r', '\n')
                else:
                    data_to_write = mimepart.body
                if data_to_write is None:
                    data_to_write = ''

                new_part.content_id = mimepart.headers.get('Content-Id')
                new_part.data = data_to_write
                self.parts.append(new_part)
        except mime.DecodingError:
            # occasionally iconv will fail via maximum recursion depth
            _log_decode_error(account.id, folder_name, mid, body_string)
            log.error('DecodeError, msg logged to {0}'.format(
                _get_errfilename(account.id, folder_name, mid)))
            return
        except RuntimeError:
            _log_decode_error(account.id, folder_name, mid, body_string)
            log.error('RuntimeError<iconv> msg logged to {0}'.format(
                _get_errfilename(account.id, folder_name, mid)))
            return

        self.calculate_sanitized_body()
        MailSyncBase.__init__(self, *args, **kwargs)

    def calculate_sanitized_body(self):
        plain_part, html_part = self.body
        # TODO: also strip signatures.
        if html_part:
            assert '\r' not in html_part, "newlines not normalized"
            stripped = extract_from_html(
                html_part.encode('utf-8')).decode('utf-8').strip()
            self.sanitized_body = unicode(stripped)
            self.calculate_html_snippet(self.sanitized_body)
        elif plain_part:
            stripped = extract_from_plain(plain_part).strip()
            self.sanitized_body = plaintext2html(stripped, False)
            self.calculate_plaintext_snippet(stripped)
        else:
            self.sanitized_body = u''
            self.snippet = u''

    def calculate_html_snippet(self, text):
        text = text.replace('<br>', ' ').replace('<br/>', ' '). \
            replace('<br />', ' ')
        text = strip_tags(text)
        self.calculate_plaintext_snippet(text)

    def calculate_plaintext_snippet(self, text):
        self.snippet = ' '.join(text.split())[:self.SNIPPET_LENGTH]

    @property
    def body(self):
        """ Returns (plaintext, html) body for the message, decoded. """
        assert self.parts, \
            "Can't calculate body before parts have been parsed"

        plain_data = None
        html_data = None

        for part in self.parts:
            if part.content_type == 'text/html':
                html_data = part.data.decode('utf-8')
                break
        for part in self.parts:
            if part.content_type == 'text/plain':
                plain_data = part.data.decode('utf-8')
                break

        return plain_data, html_data

    def trimmed_subject(self):
        s = self.subject
        if s[:4] == u'RE: ' or s[:4] == u'Re: ':
            s = s[4:]
        return s

    @property
    def prettified_body(self):
        html_data = self.sanitized_body

        prettified = None
        if 'font:' in html_data or 'font-face:' \
                in html_data or 'font-family:' in html_data:
            prettified = html_data
        else:
            prettified = """
            <html><head>
            <style rel="stylesheet" type="text/css">
            body { background-color:#FFF;
            font-family: HelveticaNeue, courier, sans-serif;
            font-size: 15px;
            color:#333;
            font-variant:normal;
            line-height:1.6em;
            font-style:normal;
            text-align:left;
            position:relative;
            margin:0;
            padding:20px; }
            a { text-decoration: underline;}
            a:hover {
             border-radius:3px; background-color: #E9E9E9;
             }
            </style>
            <base target="_blank" />
            </head><body>
            %s
            </body></html>
            """.strip() % html_data

        return prettified

    @property
    def mailing_list_info(self):
        return self.mailing_list_headers

    @property
    def headers(self):
        """ Returns headers for the message, decoded. """
        assert self.parts, \
            "Can't provide headers before parts have been parsed"

        headers = self.parts[0].data
        json_headers = json.JSONDecoder().decode(headers)

        return json_headers

    @property
    def folders(self):
        return self.thread.folders

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator,
                       'polymorphic_identity': 'message'}


class SpoolMessage(Message):
    """
    Messages created by this client.

    Stored so they are immediately available to the user. They are reconciled
    with the messages we get from the remote backend in a subsequent sync.
    """
    id = Column(Integer, ForeignKey('message.id', ondelete='CASCADE'),
                primary_key=True)

    created_date = Column(DateTime)
    is_sent = Column(Boolean, server_default=false(), nullable=False)

    state = Column(Enum('draft', 'sending', 'sending failed', 'sent'),
                   server_default='draft', nullable=False)

    # Null till reconciled.
    # Deletes should not be cascaded! i.e. delete on remote -> delete the
    # resolved_message *only*, not the original SpoolMessage we created.
    # We need this to correctly maintain draft versions (created on
    # update_draft())
    resolved_message_id = Column(Integer,
                                 ForeignKey('message.id'),
                                 nullable=True)
    resolved_message = relationship(
        'Message',
        primaryjoin='and_('
        'SpoolMessage.resolved_message_id==remote(Message.id), '
        'remote(Message.deleted_at)==None)',
        backref=backref('spooled_messages', primaryjoin='and_('
                        'remote(SpoolMessage.resolved_message_id)==Message.id,'
                        'remote(SpoolMessage.deleted_at)==None)'))

    ## FOR DRAFTS:

    # For non-conflict draft updates: versioning
    parent_draft_id = Column(Integer,
                             ForeignKey('spoolmessage.id', ondelete='CASCADE'),
                             nullable=True)
    parent_draft = relationship(
        'SpoolMessage',
        remote_side=[id],
        primaryjoin='and_('
        'SpoolMessage.parent_draft_id==remote(SpoolMessage.id), '
        'remote(SpoolMessage.deleted_at)==None)',
        backref=backref(
            'child_draft', primaryjoin='and_('
            'remote(SpoolMessage.parent_draft_id)==SpoolMessage.id,'
            'remote(SpoolMessage.deleted_at)==None)',
            uselist=False))

    # For conflict draft updates: copy of the original is created
    # We don't cascade deletes because deleting a draft should not delete
    # the other drafts that are updates to the same original.
    draft_copied_from = Column(Integer,
                               ForeignKey('spoolmessage.id'),
                               nullable=True)

    # For draft replies: the 'copy' of the thread it is a reply to.
    replyto_thread_id = Column(Integer, ForeignKey('draftthread.id',
                               ondelete='CASCADE'), nullable=True)
    replyto_thread = relationship(
        'DraftThread', primaryjoin='and_('
        'SpoolMessage.replyto_thread_id==remote(DraftThread.id),'
        'remote(DraftThread.deleted_at)==None)',
        backref=backref(
            'draftmessage', primaryjoin='and_('
            'remote(SpoolMessage.replyto_thread_id)==DraftThread.id,'
            'remote(SpoolMessage.deleted_at)==None)',
            uselist=False))

    __mapper_args__ = {'polymorphic_identity': 'spoolmessage',
                       'inherit_condition': id == Message.id}

    def __init__(self, *args, **kwargs):
        Message.__init__(self, *args, **kwargs)
        if self.inbox_uid:
            self.public_id = self.inbox_uid
