import os
import json
import datetime
import base64
from hashlib import sha256
from flanker import mime

from sqlalchemy import (Column, Integer, BigInteger, String, DateTime,
                        Boolean, Enum, ForeignKey, Text)
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.sql.expression import false

from inbox.util.html import plaintext2html, strip_tags
from inbox.sqlalchemy_ext.util import (JSON, Base36UID, generate_public_id,
                                       json_field_too_long)

from inbox.config import config
from inbox.util.addr import parse_mimepart_address_header
from inbox.util.file import mkdirp
from inbox.util.misc import parse_references, get_internaldate

from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace


from inbox.log import get_logger
log = get_logger()


def _trim_filename(s, mid, max_len=64):
    if s and len(s) > max_len:
        log.warning('filename is too long, truncating',
                    mid=mid, max_len=max_len, filename=s)
        return s[:max_len - 8] + s[-8:]  # Keep extension
    return s


def _get_errfilename(account_id, folder_name, uid):
    try:
        errdir = os.path.join(config['LOGDIR'], str(account_id), 'errors',
                              folder_name)
        errfile = os.path.join(errdir, str(uid))
        mkdirp(errdir)
    except UnicodeEncodeError:
        # Rather than wrangling character encodings, just base64-encode the
        # folder name to construct a directory.
        b64_folder_name = base64.b64encode(folder_name.encode('utf-8'))
        return _get_errfilename(account_id, b64_folder_name, uid)
    return errfile


def _log_decode_error(account_id, folder_name, uid, msg_string):
    """ msg_string is in the original encoding pulled off the wire """
    errfile = _get_errfilename(account_id, folder_name, uid)
    with open(errfile, 'w') as fh:
        fh.write(msg_string)


class Message(MailSyncBase, HasRevisions, HasPublicID):
    API_OBJECT_NAME = 'message'

    # Do delete messages if their associated thread is deleted.
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    thread_order = Column(Integer, nullable=False, default=0)

    thread = relationship(
        'Thread',
        backref=backref('messages', order_by='Message.received_date',
                        passive_deletes=True))

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          index=True, nullable=False)
    namespace = relationship(
        'Namespace',
        lazy='joined',
        load_on_pending=True)

    from_addr = Column(JSON, nullable=False, default=lambda: [])
    sender_addr = Column(JSON, nullable=True)
    reply_to = Column(JSON, nullable=True)
    to_addr = Column(JSON, nullable=False, default=lambda: [])
    cc_addr = Column(JSON, nullable=False, default=lambda: [])
    bcc_addr = Column(JSON, nullable=False, default=lambda: [])
    in_reply_to = Column(JSON, nullable=True)
    # From: http://tools.ietf.org/html/rfc4130, section 5.3.3,
    # max message_id_header is 998 characters
    message_id_header = Column(String(998), nullable=True)
    # There is no hard limit on subject limit in the spec, but 255 is common.
    subject = Column(String(255), nullable=True, default='', index=True)
    received_date = Column(DateTime, nullable=False)
    size = Column(Integer, nullable=False)
    data_sha256 = Column(String(255), nullable=True)

    is_read = Column(Boolean, server_default=false(), nullable=False)

    # For drafts (both Inbox-created and otherwise)
    is_draft = Column(Boolean, server_default=false(), nullable=False)
    is_sent = Column(Boolean, server_default=false(), nullable=False)
    state = Column(Enum('draft', 'sending', 'sending failed', 'sent'))

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

    # A reference to the block holding the full contents of the message
    full_body_id = Column(ForeignKey('block.id', name='full_body_id_fk'),
                          nullable=True)
    full_body = relationship('Block', cascade='all, delete')

    # this might be a mail-parsing bug, or just a message from a bad client
    decode_error = Column(Boolean, server_default=false(), nullable=False)

    # only on messages from Gmail (TODO: use different table)
    #
    # X-GM-MSGID is guaranteed unique across an account but not globally
    # across all Gmail.
    #
    # Messages between different accounts *may* have the same X-GM-MSGID,
    # but it's unlikely.
    #
    # (Gmail info from
    # http://mailman13.u.washington.edu/pipermail/imap-protocol/2014-July/002290.html.)
    g_msgid = Column(BigInteger, nullable=True, index=True, unique=False)
    g_thrid = Column(BigInteger, nullable=True, index=True, unique=False)

    # The uid as set in the X-INBOX-ID header of a sent message we create
    inbox_uid = Column(String(64), nullable=True, index=True)

    # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
    references = Column(JSON, nullable=True)

    # Only used on drafts
    version = Column(Base36UID, nullable=True, default=generate_public_id)

    @validates('subject')
    def validate_length(self, key, value):
        if value is None:
            return
        if len(value) > 255:
            value = value[:255]
        return value

    @classmethod
    def create_from_synced(cls, account, mid, folder_name, received_date,
                           body_string):
        """
        Parses message data and writes out db metadata and MIME blocks.

        Returns the new Message, which links to the new Part and Block objects
        through relationships. All new objects are uncommitted.

        Threads are not computed here; you gotta do that separately.

        Parameters
        ----------
        mid : int
            The account backend-specific message identifier; it's only used for
            logging errors.

        raw_message : str
            The full message including headers (encoded).

        """
        _rqd = [account, mid, folder_name, body_string]
        if not all([v is not None for v in _rqd]):
            raise ValueError(
                'Required keyword arguments: account, mid, folder_name, '
                'body_string')
        # stop trickle-down bugs
        assert account.namespace is not None
        assert not isinstance(body_string, unicode)

        msg = Message()

        try:
            msg.namespace_id = account.namespace.id
            parsed = mime.from_string(body_string)

            mime_version = parsed.headers.get('Mime-Version')
            # sometimes MIME-Version is '1.0 (1.0)', hence the .startswith()
            if mime_version is not None and not mime_version.startswith('1.0'):
                log.warning('Unexpected MIME-Version',
                            account_id=account.id, folder_name=folder_name,
                            mid=mid, mime_version=mime_version)

            msg.data_sha256 = sha256(body_string).hexdigest()

            # clean_subject strips re:, fwd: etc.
            msg.subject = parsed.clean_subject
            msg.from_addr = parse_mimepart_address_header(parsed, 'From')
            msg.sender_addr = parse_mimepart_address_header(parsed, 'Sender')
            msg.reply_to = parse_mimepart_address_header(parsed, 'Reply-To')
            msg.to_addr = parse_mimepart_address_header(parsed, 'To')
            msg.cc_addr = parse_mimepart_address_header(parsed, 'Cc')
            msg.bcc_addr = parse_mimepart_address_header(parsed, 'Bcc')

            msg.in_reply_to = parsed.headers.get('In-Reply-To')
            msg.message_id_header = parsed.headers.get('Message-Id')

            msg.received_date = received_date if received_date else \
                get_internaldate(parsed.headers.get('Date'),
                                 parsed.headers.get('Received'))

            # Custom Inbox header
            msg.inbox_uid = parsed.headers.get('X-INBOX-ID')

            # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
            msg.references = parse_references(
                parsed.headers.get('References', ''),
                parsed.headers.get('In-Reply-To', ''))

            from inbox.models.block import Block, Part
            body_block = Block()
            body_block.namespace_id = account.namespace.id
            body_block.data = body_string
            body_block.content_type = "text/plain"
            msg.full_body = body_block

            msg.size = len(body_string)  # includes headers text

            i = 0  # for walk_index

            # Store all message headers as object with index 0
            block = Block()
            block.namespace_id = account.namespace.id
            block.data = json.dumps(parsed.headers.items())

            headers_part = Part(block=block, message=msg)
            headers_part.walk_index = i

            for mimepart in parsed.walk(
                    with_self=parsed.content_type.is_singlepart()):
                i += 1
                if mimepart.content_type.is_multipart():
                    log.warning('multipart sub-part found',
                                account_id=account.id, folder_name=folder_name,
                                mid=mid)
                    continue  # TODO should we store relations?
                msg._parse_mimepart(mimepart, mid, i, account.namespace.id)

            msg.calculate_sanitized_body()
        except (mime.DecodingError, AttributeError, RuntimeError, TypeError,
                ValueError) as e:
            # Message parsing can fail for several reasons. Occasionally iconv
            # will fail via maximum recursion depth. EAS messages may be
            # missing Date and Received headers. In such cases, we still keep
            # the metadata and mark it as b0rked.
            _log_decode_error(account.id, folder_name, mid, body_string)
            err_filename = _get_errfilename(account.id, folder_name, mid)
            log.error('Message parsing error',
                      folder_name=folder_name, account_id=account.id,
                      err_filename=err_filename, error=e)
            msg._mark_error()

        # Occasionally people try to send messages to way too many
        # recipients. In such cases, empty the field and treat as a parsing
        # error so that we don't break the entire sync.
        for field in ('to_addr', 'cc_addr', 'bcc_addr', 'references'):
            value = getattr(msg, field)
            if json_field_too_long(value):
                _log_decode_error(account.id, folder_name, mid, body_string)
                err_filename = _get_errfilename(account.id, folder_name, mid)
                log.error('Recipient field too long', field=field,
                          account_id=account.id, folder_name=folder_name,
                          mid=mid)
                setattr(msg, field, [])
                msg._mark_error()

        return msg

    def _parse_mimepart(self, mimepart, mid, index, namespace_id):
        """Parse a single MIME part into a Block and Part object linked to this
        message."""
        from inbox.models.block import Block, Part
        block = Block()
        block.namespace_id = namespace_id
        block.content_type = mimepart.content_type.value
        block.filename = _trim_filename(
            mimepart.content_type.params.get('name'), mid)

        new_part = Part(block=block, message=self)
        new_part.walk_index = index

        # TODO maybe also trim other headers?
        if mimepart.content_disposition[0] is not None:
            value, params = mimepart.content_disposition
            if value not in ['inline', 'attachment']:
                cd = mimepart.content_disposition
                log.error('Unknown Content-Disposition',
                          mid=mid, bad_content_disposition=cd,
                          parsed_content_disposition=value)
                return
            else:
                new_part.content_disposition = value
                if value == 'attachment':
                    new_part.block.filename = _trim_filename(
                        params.get('filename'), mid)

        if mimepart.body is None:
            data_to_write = ''
        elif new_part.block.content_type.startswith('text'):
            data_to_write = mimepart.body.encode('utf-8', 'strict')
            # normalize mac/win/unix newlines
            data_to_write = data_to_write.replace('\r\n', '\n'). \
                replace('\r', '\n')
        else:
            data_to_write = mimepart.body
        if data_to_write is None:
            data_to_write = ''

        new_part.content_id = mimepart.headers.get('Content-Id')

        block.data = data_to_write

    def _mark_error(self):
        self.decode_error = True
        # fill in required attributes with filler data if could not parse them
        self.size = 0
        if self.received_date is None:
            self.received_date = datetime.datetime.utcnow()
        if self.sanitized_body is None:
            self.sanitized_body = ''
        if self.snippet is None:
            self.snippet = ''

    def calculate_sanitized_body(self):
        plain_part, html_part = self.body
        # TODO: also strip signatures.
        if html_part:
            assert '\r' not in html_part, "newlines not normalized"
            self.snippet = self.calculate_html_snippet(html_part)
            self.sanitized_body = html_part
        elif plain_part:
            self.snippet = self.calculate_plaintext_snippet(plain_part)
            self.sanitized_body = plaintext2html(plain_part, False)
        else:
            self.sanitized_body = u''
            self.snippet = u''

    def calculate_html_snippet(self, text):
        text = text.replace('<br>', ' ').replace('<br/>', ' '). \
            replace('<br />', ' ')
        text = strip_tags(text)
        return self.calculate_plaintext_snippet(text)

    def calculate_plaintext_snippet(self, text):
        return ' '.join(text.split())[:self.SNIPPET_LENGTH]

    @property
    def body(self):
        """ Returns (plaintext, html) body for the message, decoded. """
        assert self.parts, \
            "Can't calculate body before parts have been parsed"

        plain_data = None
        html_data = None

        for part in self.parts:
            if part.block.content_type == 'text/html':
                html_data = part.block.data.decode('utf-8').strip()
                break
        for part in self.parts:
            if part.block.content_type == 'text/plain':
                plain_data = part.block.data.decode('utf-8').strip()
                break

        return plain_data, html_data

    # FIXME @karim: doesn't work - refactor/i18n
    def trimmed_subject(self):
        s = self.subject
        if s[:4] == u'RE: ' or s[:4] == u'Re: ':
            s = s[4:]
        return s

    @property
    def headers(self):
        """ Returns headers for the message, decoded. """
        assert self.parts, \
            "Can't provide headers before parts have been parsed"

        headers = self.parts[0].block.data
        json_headers = json.JSONDecoder().decode(headers)

        return json_headers

    @property
    def folders(self):
        return self.thread.folders

    @property
    def attachments(self):
        return [part for part in self.parts if part.is_attachment]

    @property
    def api_attachment_metadata(self):
        resp = []
        for part in self.parts:
            if not part.is_attachment:
                continue
            k = {'content_type': part.block.content_type,
                 'size': part.block.size,
                 'filename': part.block.filename,
                 'id': part.block.public_id}
            content_id = part.content_id
            if content_id:
                if content_id[0] == '<' and content_id[-1] == '>':
                    content_id = content_id[1:-1]
                k['content_id'] = content_id
            resp.append(k)
        return resp

    # FOR INBOX-CREATED MESSAGES:

    is_created = Column(Boolean, server_default=false(), nullable=False)

    # Whether this draft is a reply to an existing thread.
    is_reply = Column(Boolean)

    # Deprecated
    # TODO(emfree): remove from schema
    resolved_message_id = Column(Integer, ForeignKey('message.id'),
                                 nullable=True)

    @property
    def versioned_relationships(self):
        return ['parts']
