import json
import datetime
import itertools
from hashlib import sha256
from flanker import mime
from collections import defaultdict

from sqlalchemy import (Column, Integer, BigInteger, String, DateTime,
                        Boolean, Enum, ForeignKey, Text, Index)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.sql.expression import false

from inbox.util.html import plaintext2html, strip_tags
from inbox.sqlalchemy_ext.util import JSON, json_field_too_long

from inbox.util.addr import parse_mimepart_address_header
from inbox.util.misc import parse_references, get_internaldate

from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace
from inbox.security.blobstorage import encode_blob, decode_blob


from inbox.log import get_logger
log = get_logger()


def _trim_filename(s, mid, max_len=64):
    if s and len(s) > max_len:
        log.warning('filename is too long, truncating',
                    mid=mid, max_len=max_len, filename=s)
        return s[:max_len - 8] + s[-8:]  # Keep extension
    return s


class Message(MailSyncBase, HasRevisions, HasPublicID):
    @property
    def API_OBJECT_NAME(self):
        return 'message' if not self.is_draft else 'draft'

    # Do delete messages if their associated thread is deleted.
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)

    thread = relationship(
        'Thread',
        backref=backref('messages', order_by='Message.received_date',
                        passive_deletes=True, cascade='all, delete-orphan'))

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
    subject = Column(String(255), nullable=True, default='')
    received_date = Column(DateTime, nullable=False, index=True)
    size = Column(Integer, nullable=False)
    data_sha256 = Column(String(255), nullable=True)

    is_read = Column(Boolean, server_default=false(), nullable=False)

    # For drafts (both Inbox-created and otherwise)
    is_draft = Column(Boolean, server_default=false(), nullable=False)
    is_sent = Column(Boolean, server_default=false(), nullable=False)

    # DEPRECATED
    state = Column(Enum('draft', 'sending', 'sending failed', 'sent'))

    # DEPRECATED
    _sanitized_body = Column('sanitized_body', Text(length=26214400),
                             nullable=False, default='')
    _compacted_body = Column(LONGBLOB, nullable=True)
    snippet = Column(String(191), nullable=False)
    SNIPPET_LENGTH = 191

    # A reference to the block holding the full contents of the message
    full_body_id = Column(ForeignKey('block.id', name='full_body_id_fk'),
                          nullable=True)
    full_body = relationship('Block', cascade='all, delete')

    # this might be a mail-parsing bug, or just a message from a bad client
    decode_error = Column(Boolean, server_default=false(), nullable=False,
                          index=True)

    # only on messages from Gmail (TODO: use different table)
    #
    # X-GM-MSGID is guaranteed unique across an account but not globally
    # across all Gmail.
    #
    # Messages between different accounts *may* have the same X-GM-MSGID,
    # but it's unlikely.
    #
    # (Gmail info from
    # http://mailman13.u.washington.edu/pipermail/imap-protocol/
    # 2014-July/002290.html.)
    g_msgid = Column(BigInteger, nullable=True, index=True, unique=False)
    g_thrid = Column(BigInteger, nullable=True, index=True, unique=False)

    # The uid as set in the X-INBOX-ID header of a sent message we create
    inbox_uid = Column(String(64), nullable=True, index=True)

    def regenerate_inbox_uid(self):
        """The value of inbox_uid is simply the draft public_id and version,
        concatenated. Because the inbox_uid identifies the draft on the remote
        provider, we regenerate it on each draft revision so that we can delete
        the old draft and add the new one on the remote."""
        self.inbox_uid = '{}-{}'.format(self.public_id, self.version)

    # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
    references = Column(JSON, nullable=True)

    # Only used for drafts.
    version = Column(Integer, nullable=False, server_default='0')

    def mark_for_deletion(self):
        """Mark this message to be deleted by an asynchronous delete
        handler."""
        self.deleted_at = datetime.datetime.utcnow()

    @validates('subject')
    def sanitize_subject(self, key, value):
        # Trim overlong subjects, and remove null bytes. The latter can result
        # when, for example, UTF-8 text decoded from an RFC2047-encoded header
        # contains null bytes.
        if value is None:
            return
        if len(value) > 255:
            value = value[:255]
        value = value.replace('\0', '')
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

        from inbox.models.block import Block, Part
        body_block = Block()
        body_block.namespace_id = account.namespace.id
        body_block.data = body_string
        body_block.content_type = "text/plain"
        msg.full_body = body_block

        msg.namespace_id = account.namespace.id

        try:
            parsed = mime.from_string(body_string)

            i = 0  # for walk_index

            # Store all message headers as object with index 0
            block = Block()
            block.namespace_id = account.namespace.id
            block.data = json.dumps(parsed.headers.items())

            headers_part = Part(block=block, message=msg)
            headers_part.walk_index = i

            msg._parse_metadata(parsed, body_string, received_date, account.id,
                                folder_name, mid)
        except (mime.DecodingError, AttributeError, RuntimeError, TypeError,
                ValueError) as e:
            parsed = None
            log.error('Error parsing message metadata',
                      folder_name=folder_name, account_id=account.id, error=e)
            msg._mark_error()

        if parsed is not None:
            for mimepart in parsed.walk(
                    with_self=parsed.content_type.is_singlepart()):
                i += 1
                try:
                    if mimepart.content_type.is_multipart():
                        log.warning('multipart sub-part found',
                                    account_id=account.id,
                                    folder_name=folder_name,
                                    mid=mid)
                        continue  # TODO should we store relations?
                    msg._parse_mimepart(mimepart, mid, i, account.namespace.id)
                except (mime.DecodingError, AttributeError, RuntimeError,
                        TypeError, ValueError) as e:
                    log.error('Error parsing message MIME parts',
                              folder_name=folder_name, account_id=account.id,
                              error=e)
                    msg._mark_error()
            msg.calculate_body()

            # Occasionally people try to send messages to way too many
            # recipients. In such cases, empty the field and treat as a parsing
            # error so that we don't break the entire sync.
            for field in ('to_addr', 'cc_addr', 'bcc_addr', 'references'):
                value = getattr(msg, field)
                if json_field_too_long(value):
                    log.error('Recipient field too long', field=field,
                              account_id=account.id, folder_name=folder_name,
                              mid=mid)
                    setattr(msg, field, [])
                    msg._mark_error()

        return msg

    def _parse_metadata(self, parsed, body_string, received_date,
                        account_id, folder_name, mid):
        mime_version = parsed.headers.get('Mime-Version')
        # sometimes MIME-Version is '1.0 (1.0)', hence the .startswith()
        if mime_version is not None and not mime_version.startswith('1.0'):
            log.warning('Unexpected MIME-Version',
                        account_id=account_id, folder_name=folder_name,
                        mid=mid, mime_version=mime_version)

        self.data_sha256 = sha256(body_string).hexdigest()

        self.subject = parsed.subject
        self.from_addr = parse_mimepart_address_header(parsed, 'From')
        self.sender_addr = parse_mimepart_address_header(parsed, 'Sender')
        self.reply_to = parse_mimepart_address_header(parsed, 'Reply-To')
        self.to_addr = parse_mimepart_address_header(parsed, 'To')
        self.cc_addr = parse_mimepart_address_header(parsed, 'Cc')
        self.bcc_addr = parse_mimepart_address_header(parsed, 'Bcc')

        self.in_reply_to = parsed.headers.get('In-Reply-To')
        self.message_id_header = parsed.headers.get('Message-Id')

        self.received_date = received_date if received_date else \
            get_internaldate(parsed.headers.get('Date'),
                                parsed.headers.get('Received'))

        # Custom Inbox header
        self.inbox_uid = parsed.headers.get('X-INBOX-ID')

        # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
        self.references = parse_references(
            parsed.headers.get('References', ''),
            parsed.headers.get('In-Reply-To', ''))

        self.size = len(body_string)  # includes headers text

    def _parse_mimepart(self, mimepart, mid, index, namespace_id):
        """Parse a single MIME part into a Block and Part object linked to this
        message."""
        from inbox.models.block import Block, Part
        disposition, disposition_params = mimepart.content_disposition
        if (disposition is not None and
                disposition not in ['inline', 'attachment']):
            cd = mimepart.content_disposition
            log.error('Unknown Content-Disposition',
                      mid=mid, bad_content_disposition=cd,
                      parsed_content_disposition=disposition)
            self._mark_error()
            return
        block = Block()
        block.namespace_id = namespace_id
        block.content_type = mimepart.content_type.value
        block.filename = _trim_filename(
            mimepart.content_type.params.get('name'), mid)

        new_part = Part(block=block)
        new_part.walk_index = index

        # TODO maybe also trim other headers?
        if disposition is not None:
            new_part.content_disposition = disposition
            if disposition == 'attachment':
                new_part.block.filename = _trim_filename(
                    disposition_params.get('filename'), mid)

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

        # Wait until end so we don't create incomplete blocks/parts for MIME
        # parts which fail to parse.
        new_part.message = self

    def _mark_error(self):
        """ Mark message as having encountered errors while parsing.

        Message parsing can fail for several reasons. Occasionally iconv will
        fail via maximum recursion depth. EAS messages may be missing Date and
        Received headers. Flanker may fail to handle some out-of-spec messages.

        In this case, we keep what metadata we've managed to parse but also
        mark the message as having failed to parse properly.

        """
        self.decode_error = True
        # fill in required attributes with filler data if could not parse them
        self.size = 0
        if self.received_date is None:
            self.received_date = datetime.datetime.utcnow()
        if self.body is None:
            self.body = ''
        if self.snippet is None:
            self.snippet = ''

    def calculate_body(self):
        plain_part, html_part = self.body_parts
        # TODO: also strip signatures.
        if html_part:
            assert '\r' not in html_part, "newlines not normalized"
            self.snippet = self.calculate_html_snippet(html_part)
            self.body = html_part
        elif plain_part:
            self.snippet = self.calculate_plaintext_snippet(plain_part)
            self.body = plaintext2html(plain_part, False)
        else:
            self.body = u''
            self.snippet = u''

    def calculate_html_snippet(self, text):
        text = strip_tags(text)
        return self.calculate_plaintext_snippet(text)

    def calculate_plaintext_snippet(self, text):
        return ' '.join(text.split())[:self.SNIPPET_LENGTH]

    @property
    def body_parts(self):
        """ Returns (plaintext, html) body parts for the message, decoded. """
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

    @property
    def body(self):
        if self._compacted_body is None:
            # Return from legacy _sanitized_body column to support online data
            # migration.
            return self._sanitized_body
        return decode_blob(self._compacted_body).decode('utf-8')

    @body.setter
    def body(self, value):
        if value is None:
            self._compacted_body = None
        else:
            self._compacted_body = encode_blob(value.encode('utf-8'))
            # Also write to the _sanitized_body column for now, so there's no
            # possibility that concurrent data migration from
            # _sanitized_body --> _compacted_body accidentally ends up writing
            # an empty value to _compacted_body
            self._sanitized_body = value

    @property
    def participants(self):
        """
        Different messages in the thread may reference the same email
        address with different phrases. We partially deduplicate: if the same
        email address occurs with both empty and nonempty phrase, we don't
        separately return the (empty phrase, address) pair.

        """
        deduped_participants = defaultdict(set)
        chain = []
        if self.from_addr:
            chain.append(self.from_addr)

        if self.to_addr:
            chain.append(self.to_addr)

        if self.cc_addr:
            chain.append(self.cc_addr)

        if self.bcc_addr:
            chain.append(self.bcc_addr)

        for phrase, address in itertools.chain.from_iterable(chain):
            deduped_participants[address].add(phrase.strip())

        p = []
        for address, phrases in deduped_participants.iteritems():
            for phrase in phrases:
                if phrase != '' or len(phrases) == 1:
                    p.append((phrase, address))
        return p

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

    reply_to_message_id = Column(Integer, ForeignKey('message.id'),
                                 nullable=True)
    reply_to_message = relationship('Message', uselist=False)

    @property
    def versioned_relationships(self):
        return ['parts']

    @property
    def has_attached_events(self):
        return 'text/calendar' in [p.block.content_type for p in self.parts]

    @property
    def attached_event_files(self):
        return [part for part in self.parts
                if part.block.content_type == 'text/calendar']


# Need to explicitly specify the index length for table generation with MySQL
# 5.6 when columns are too long to be fully indexed with utf8mb4 collation.
Index('ix_message_subject', Message.subject, mysql_length=191)
Index('ix_message_data_sha256', Message.data_sha256, mysql_length=191)

# For API querying performance.
Index('ix_message_ns_id_is_draft_received_date', Message.namespace_id,
      Message.is_draft, Message.received_date)

# For async deletion.
Index('ix_message_namespace_id_deleted_at', Message.namespace_id,
      Message.deleted_at)
