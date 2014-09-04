import os
import json
import datetime

from hashlib import sha256
from flanker import mime

from sqlalchemy import (Column, Integer, BigInteger, String, DateTime,
                        Boolean, Enum, ForeignKey, Text)
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.sql.expression import false

from inbox.util.html import (plaintext2html, strip_tags,
                             extract_from_html, extract_from_plain)
from inbox.sqlalchemy_ext.util import (JSON, Base36UID, generate_public_id,
                                       BigJSON)

from inbox.config import config
from inbox.util.addr import parse_email_address_list
from inbox.util.file import mkdirp
from inbox.util.misc import parse_references, get_internaldate

from inbox.models.mixins import HasPublicID
from inbox.models.transaction import HasRevisions
from inbox.models.base import MailSyncBase


from inbox.log import get_logger
log = get_logger()


def _trim_filename(s, account_id, mid, max_len=64):
    if s and len(s) > max_len:
        log.warning('filename is too long, truncating',
                    account_id=account_id, mid=mid, max_len=max_len,
                    filename=s)
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
    # Do delete messages if their associated thread is deleted.
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    thread_order = Column(Integer, nullable=False, default=0)

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

    from_addr = Column(JSON, nullable=False, default=lambda: [])
    sender_addr = Column(JSON, nullable=True)
    reply_to = Column(JSON, nullable=True)

    # We allow to_addr to be bigger rather than truncating,
    # it may be used in sending.
    to_addr = Column(BigJSON, nullable=False, default=lambda: [])

    cc_addr = Column(JSON, nullable=False, default=lambda: [])
    bcc_addr = Column(JSON, nullable=False, default=lambda: [])
    in_reply_to = Column(JSON, nullable=True)
    # From: http://tools.ietf.org/html/rfc4130, section 5.3.3,
    # max message_id_header is 998 characters
    message_id_header = Column(String(998), nullable=True)
    # There is no hard limit on subject limit in the spec, but 255 is common.
    subject = Column(String(255), nullable=True)
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
    inbox_uid = Column(String(64), nullable=True)

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
        _rqd = [account, mid, folder_name, flags, body_string]

        MailSyncBase.__init__(self, *args, **kwargs)

        # for drafts
        if not any(_rqd):
            return

        if any(_rqd) and not all([v is not None for v in _rqd]):
            raise ValueError(
                "Required keyword arguments: account, mid, folder_name, "
                "flags, body_string")

        # stop trickle-down bugs
        assert account.namespace is not None
        assert not isinstance(body_string, unicode)

        try:
            parsed = mime.from_string(body_string)

            mime_version = parsed.headers.get('Mime-Version')
            # sometimes MIME-Version is "1.0 (1.0)", hence the .startswith()
            if mime_version is not None and not mime_version.startswith('1.0'):
                log.warning('Unexpected MIME-Version',
                            account_id=account.id, folder_name=folder_name,
                            mid=mid, mime_version=mime_version)

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
                    log.warning('multipart sub-part found',
                                account_id=account.id, folder_name=folder_name,
                                mid=mid)
                    continue  # TODO should we store relations?

                new_part = Part()
                new_part.namespace_id = account.namespace.id
                new_part.message = self
                new_part.walk_index = i
                new_part.content_type = mimepart.content_type.value
                new_part.filename = _trim_filename(
                    mimepart.content_type.params.get('name'),
                    account.id, mid)
                # TODO maybe also trim other headers?

                if mimepart.content_disposition[0] is not None:
                    value, params = mimepart.content_disposition
                    if value not in ['inline', 'attachment']:
                        log.error('Unknown Content-Disposition',
                                  account_id=account.id, mid=mid,
                                  folder_name=folder_name,
                                  bad_content_disposition=
                                  mimepart.content_disposition,
                                  parsed_content_disposition=value)
                        continue
                    else:
                        new_part.content_disposition = value
                        if value == 'attachment':
                            new_part.filename = _trim_filename(
                                params.get('filename'), account.id, mid)

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
            self.calculate_sanitized_body()
        except mime.DecodingError:
            # Occasionally iconv will fail via maximum recursion depth. We
            # still keep the metadata and mark it as b0rked.
            _log_decode_error(account.id, folder_name, mid, body_string)
            log.error('Message parsing DecodeError', account_id=account.id,
                      folder_name=folder_name, err_filename=_get_errfilename(
                          account.id, folder_name, mid))
            self.mark_error()
            return
        except AttributeError:
            # For EAS messages that are missing Date + Received headers, due
            # to the processing we do in inbox.util.misc.get_internaldate()
            _log_decode_error(account.id, folder_name, mid, body_string)
            log.error('Message parsing AttributeError', account_id=account.id,
                      folder_name=folder_name, err_filename=_get_errfilename(
                          account.id, folder_name, mid))
            self.mark_error()
            return
        except RuntimeError:
            _log_decode_error(account.id, folder_name, mid, body_string)
            log.error('Message parsing RuntimeError<iconv>'.format(
                err_filename=_get_errfilename(account.id, folder_name, mid)))
            self.mark_error()
            return

    def mark_error(self):
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

    # FIXME @karim: doesn't work - refactor/i18n
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

    @property
    def attachments(self):
        return [part for part in self.parts if part.is_attachment]

    ## FOR INBOX-CREATED MESSAGES:

    is_created = Column(Boolean, server_default=false(), nullable=False)

    # Whether this draft is a reply to an existing thread.
    is_reply = Column(Boolean)

    # Null till reconciled.
    # Deletes should not be cascaded! i.e. delete on remote -> delete the
    # resolved_message *only*, not the original Message we created.
    # We need this to correctly maintain draft versions (created on
    # update_draft())
    resolved_message_id = Column(Integer,
                                 ForeignKey('message.id'),
                                 nullable=True)
    resolved_message = relationship(
        'Message',
        remote_side='Message.id',
        primaryjoin='and_('
        'Message.resolved_message_id==remote(Message.id), '
        'remote(Message.deleted_at)==None)',
        backref=backref('created_messages', primaryjoin='and_('
                        'remote(Message.resolved_message_id)==Message.id,'
                        'remote(Message.deleted_at)==None)',
                        uselist=False))

    @classmethod
    def create_draft_message(cls, *args, **kwargs):
        obj = cls(*args, **kwargs)
        obj.is_created = True
        obj.is_draft = True
        obj.state = 'draft'
        if obj.inbox_uid:
            obj.public_id = obj.inbox_uid
        return obj
