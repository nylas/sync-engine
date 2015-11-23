import binascii
import datetime
import itertools
from hashlib import sha256
from collections import defaultdict

from flanker import mime
from sqlalchemy import (Column, Integer, BigInteger, String, DateTime,
                        Boolean, Enum, ForeignKey, Index, bindparam)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import (relationship, backref, validates, joinedload,
                            subqueryload, load_only)
from sqlalchemy.sql.expression import false
from sqlalchemy.ext.associationproxy import association_proxy

from nylas.logging import get_logger
log = get_logger()
from inbox.util.html import plaintext2html, strip_tags
from inbox.sqlalchemy_ext.util import JSON, json_field_too_long, bakery
from inbox.util.addr import parse_mimepart_address_header
from inbox.util.misc import parse_references, get_internaldate
from inbox.util.blockstore import save_to_blockstore
from inbox.security.blobstorage import encode_blob, decode_blob
from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace
from inbox.models.category import Category


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

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          index=True, nullable=False)
    namespace = relationship(
        'Namespace',
        load_on_pending=True)

    # Do delete messages if their associated thread is deleted.
    thread_id = Column(ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    thread = relationship(
        'Thread',
        backref=backref('messages', order_by='Message.received_date',
                        passive_deletes=True, cascade='all, delete-orphan'))

    from_addr = Column(JSON, nullable=False, default=lambda: [])
    sender_addr = Column(JSON, nullable=True)
    reply_to = Column(JSON, nullable=True, default=lambda: [])
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
    is_starred = Column(Boolean, server_default=false(), nullable=False)

    # For drafts (both Inbox-created and otherwise)
    is_draft = Column(Boolean, server_default=false(), nullable=False)
    is_sent = Column(Boolean, server_default=false(), nullable=False)

    # REPURPOSED
    state = Column(Enum('draft', 'sending', 'sending failed', 'sent',
                        'actions_pending', 'actions_committed'))

    @property
    def categories_changes(self):
        return self.state == 'actions_pending'

    @categories_changes.setter
    def categories_changes(self, has_changes):
        if has_changes is True:
            self.state = 'actions_pending'
        else:
            self.state = 'actions_committed'

    _compacted_body = Column(LONGBLOB, nullable=True)
    snippet = Column(String(191), nullable=False)
    SNIPPET_LENGTH = 191

    # this might be a mail-parsing bug, or just a message from a bad client
    decode_error = Column(Boolean, server_default=false(), nullable=False,
                          index=True)

    # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
    references = Column(JSON, nullable=True)

    # Only used for drafts.
    version = Column(Integer, nullable=False, server_default='0')

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
        """
        The value of inbox_uid is simply the draft public_id and version,
        concatenated. Because the inbox_uid identifies the draft on the remote
        provider, we regenerate it on each draft revision so that we can delete
        the old draft and add the new one on the remote."""

        from inbox.sendmail.message import generate_message_id_header
        self.inbox_uid = '{}-{}'.format(self.public_id, self.version)
        self.message_id_header = generate_message_id_header(self.inbox_uid)

    categories = association_proxy(
        'messagecategories', 'category',
        creator=lambda category: MessageCategory(category=category))

    # FOR INBOX-CREATED MESSAGES:

    is_created = Column(Boolean, server_default=false(), nullable=False)

    # Whether this draft is a reply to an existing thread.
    is_reply = Column(Boolean)

    reply_to_message_id = Column(ForeignKey('message.id'), nullable=True)
    reply_to_message = relationship('Message', uselist=False)

    def mark_for_deletion(self):
        """
        Mark this message to be deleted by an asynchronous delete
        handler.

        """
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

        msg.data_sha256 = sha256(body_string).hexdigest()

        # Persist the raw MIME message to disk/ S3
        save_to_blockstore(msg.data_sha256, body_string)

        # Persist the processed message to the database
        msg.namespace_id = account.namespace.id

        try:
            parsed = mime.from_string(body_string)
            # Non-persisted instance attribute used by EAS.
            msg.parsed_body = parsed
            msg._parse_metadata(parsed, body_string, received_date, account.id,
                                folder_name, mid)
        except (mime.DecodingError, AttributeError, RuntimeError,
                TypeError) as e:
            parsed = None
            # Non-persisted instance attribute used by EAS.
            msg.parsed_body = ''
            log.error('Error parsing message metadata',
                      folder_name=folder_name, account_id=account.id, error=e)
            msg._mark_error()

        if parsed is not None:
            plain_parts = []
            html_parts = []
            for mimepart in parsed.walk(
                    with_self=parsed.content_type.is_singlepart()):
                try:
                    if mimepart.content_type.is_multipart():
                        continue  # TODO should we store relations?
                    msg._parse_mimepart(mid, mimepart, account.namespace.id,
                                        html_parts, plain_parts)
                except (mime.DecodingError, AttributeError, RuntimeError,
                        TypeError, binascii.Error, UnicodeDecodeError) as e:
                    log.error('Error parsing message MIME parts',
                              folder_name=folder_name, account_id=account.id,
                              error=e)
                    msg._mark_error()
            msg.calculate_body(html_parts, plain_parts)

            # Occasionally people try to send messages to way too many
            # recipients. In such cases, empty the field and treat as a parsing
            # error so that we don't break the entire sync.
            for field in ('to_addr', 'cc_addr', 'bcc_addr', 'references',
                          'reply_to'):
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

        self.subject = parsed.subject
        self.from_addr = parse_mimepart_address_header(parsed, 'From')
        self.sender_addr = parse_mimepart_address_header(parsed, 'Sender')
        self.reply_to = parse_mimepart_address_header(parsed, 'Reply-To')
        self.to_addr = parse_mimepart_address_header(parsed, 'To')
        self.cc_addr = parse_mimepart_address_header(parsed, 'Cc')
        self.bcc_addr = parse_mimepart_address_header(parsed, 'Bcc')

        self.in_reply_to = parsed.headers.get('In-Reply-To')

        # The RFC mandates that the Message-Id header must be at most 998
        # characters. Sadly, not everybody follows specs.
        self.message_id_header = parsed.headers.get('Message-Id')
        if self.message_id_header and len(self.message_id_header) > 998:
            self.message_id_header = self.message_id_header[:998]
            log.warning('Message-Id header too long. Truncating',
                        parsed.headers.get('Message-Id'),
                        logstash_tag='truncated_message_id')

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

    def _parse_mimepart(self, mid, mimepart, namespace_id, html_parts,
                        plain_parts):
        disposition, _ = mimepart.content_disposition
        content_id = mimepart.headers.get('Content-Id')
        content_type, params = mimepart.content_type

        filename = mimepart.detected_file_name
        if filename == '':
            filename = None

        is_text = content_type.startswith('text')
        if disposition not in (None, 'inline', 'attachment'):
            log.error('Unknown Content-Disposition',
                      message_public_id=self.public_id,
                      bad_content_disposition=mimepart.content_disposition)
            self._mark_error()
            return

        if disposition == 'attachment':
            self._save_attachment(mimepart, disposition, content_type,
                                  filename, content_id, namespace_id, mid)
            return

        if (disposition == 'inline' and
                not (is_text and filename is None and content_id is None)):
            # Some clients set Content-Disposition: inline on text MIME parts
            # that we really want to treat as part of the text body. Don't
            # treat those as attachments.
            self._save_attachment(mimepart, disposition, content_type,
                                  filename, content_id, namespace_id, mid)
            return

        if is_text:
            if mimepart.body is None:
                return
            normalized_data = mimepart.body.encode('utf-8', 'strict')
            normalized_data = normalized_data.replace('\r\n', '\n'). \
                replace('\r', '\n')
            if content_type == 'text/html':
                html_parts.append(normalized_data)
            elif content_type == 'text/plain':
                plain_parts.append(normalized_data)
            else:
                log.info('Saving other text MIME part as attachment',
                         content_type=content_type, mid=mid)
                self._save_attachment(mimepart, 'attachment', content_type,
                                      filename, content_id, namespace_id, mid)
            return

        # Finally, if we get a non-text MIME part without Content-Disposition,
        # treat it as an attachment.
        self._save_attachment(mimepart, 'attachment', content_type,
                              filename, content_id, namespace_id, mid)

    def _save_attachment(self, mimepart, content_disposition, content_type,
                         filename, content_id, namespace_id, mid):
        from inbox.models import Part, Block
        block = Block()
        block.namespace_id = namespace_id
        block.filename = _trim_filename(filename, mid=mid)
        block.content_type = content_type
        part = Part(block=block, message=self)
        if content_id:
            content_id = content_id[:255]
        part.content_id = content_id
        part.content_disposition = content_disposition
        data = mimepart.body or ''
        if isinstance(data, unicode):
            data = data.encode('utf-8', 'strict')
        block.data = data

    def _mark_error(self):
        """
        Mark message as having encountered errors while parsing.

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

    def calculate_body(self, html_parts, plain_parts):
        html_body = ''.join(html_parts).decode('utf-8').strip()
        plain_body = '\n'.join(plain_parts).decode('utf-8').strip()
        if html_body:
            self.snippet = self.calculate_html_snippet(html_body)
            self.body = html_body
        elif plain_body:
            self.snippet = self.calculate_plaintext_snippet(plain_body)
            self.body = plaintext2html(plain_body, False)
        else:
            self.body = u''
            self.snippet = u''

    def calculate_html_snippet(self, text):
        text = strip_tags(text)
        return self.calculate_plaintext_snippet(text)

    def calculate_plaintext_snippet(self, text):
        return ' '.join(text.split())[:self.SNIPPET_LENGTH]

    @property
    def body(self):
        if self._compacted_body is None:
            return None
        return decode_blob(self._compacted_body).decode('utf-8')

    @body.setter
    def body(self, value):
        if value is None:
            self._compacted_body = None
        else:
            self._compacted_body = encode_blob(value.encode('utf-8'))

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

    @property
    def versioned_relationships(self):
        return ['parts']

    @property
    def propagated_attributes(self):
        return ['is_read', 'is_starred', 'messagecategories']

    @property
    def has_attached_events(self):
        return 'text/calendar' in [p.block.content_type for p in self.parts]

    @property
    def attached_event_files(self):
        return [part for part in self.parts
                if part.block.content_type == 'text/calendar']

    @property
    def account(self):
        return self.namespace.account

    def get_header(self, header, mid):
        if self.decode_error:
            log.warning('Error getting message header', mid=mid)
            return
        return self.parsed_body.headers.get(header)

    @classmethod
    def from_public_id(cls, public_id, namespace_id, db_session):
        q = bakery(lambda s: s.query(cls))
        q += lambda q: q.filter(
            Message.public_id == bindparam('public_id'),
            Message.namespace_id == bindparam('namespace_id'))
        q += lambda q: q.options(
            joinedload(Message.thread).load_only('discriminator', 'public_id'),
            joinedload(Message.messagecategories).joinedload('category'),
            joinedload(Message.parts).joinedload('block'),
            joinedload(Message.events))
        return q(db_session).params(
            public_id=public_id, namespace_id=namespace_id).one()

    @classmethod
    def api_loading_options(cls, expand=False):
        columns = ['public_id', 'is_draft', 'from_addr', 'to_addr', 'cc_addr',
                   'bcc_addr', 'is_read', 'is_starred', 'received_date',
                   'is_sent', 'subject', 'snippet', 'version', 'from_addr',
                   'to_addr', 'cc_addr', 'bcc_addr', 'reply_to',
                   '_compacted_body', 'thread_id', 'namespace_id']
        if expand:
            columns += ['message_id_header', 'in_reply_to', 'references']
        return (
            load_only(*columns),
            subqueryload('parts').joinedload('block'),
            subqueryload('thread').load_only('public_id', 'discriminator'),
            subqueryload('events').load_only('public_id', 'discriminator'),
            subqueryload('messagecategories').joinedload('category')
        )


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

# For statistics about messages sent via Nylas
Index('ix_message_namespace_id_is_created', Message.namespace_id,
      Message.is_created)

Index('ix_message_namespace_id_message_id_header_subject',
      Message.namespace_id, Message.subject, Message.message_id_header,
      mysql_length={'subject': 191, 'message_id_header': 191})


class MessageCategory(MailSyncBase):
    """ Mapping between messages and categories. """
    message_id = Column(ForeignKey(Message.id, ondelete='CASCADE'),
                        nullable=False)
    message = relationship(
        'Message',
        backref=backref('messagecategories',
                        collection_class=set,
                        cascade='all, delete-orphan'))

    category_id = Column(ForeignKey(Category.id, ondelete='CASCADE'),
                         nullable=False)
    category = relationship(
        Category,
        backref=backref('messagecategories',
                        cascade='all, delete-orphan',
                        lazy='dynamic'))

    @property
    def namespace(self):
        return self.message.namespace

Index('message_category_ids',
      MessageCategory.message_id, MessageCategory.category_id)
