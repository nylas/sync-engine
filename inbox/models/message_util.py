""" Message-related functions. """
import os
import json

from hashlib import sha256

from flanker import mime
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.util.addr import parse_email_address_list
from inbox.util.file import mkdirp
from inbox.util.misc import parse_ml_headers, parse_references

from inbox.models.tables.base import Message, SpoolMessage, Part
from inbox.config import config


def trim_filename(s, max_len=64, log=None):
    if s and len(s) > max_len:
        if log:
            log.warning(u"field is too long. Truncating to {}"
                        u"characters. {}".format(max_len, s))
        return s[:max_len - 8] + s[-8:]  # Keep extension
    return s


def get_errfilename(account_id, folder_name, uid):
    errdir = os.path.join(config['LOGDIR'], str(account_id), 'errors',
                          folder_name)
    errfile = os.path.join(errdir, str(uid))
    mkdirp(errdir)
    return errfile


def log_decode_error(account_id, folder_name, uid, msg_string):
    """ msg_string is in the original encoding pulled off the wire """
    errfile = get_errfilename(account_id, folder_name, uid)
    with open(errfile, 'w') as fh:
        fh.write(msg_string)


def create_message(db_session, log, account, mid, folder_name, received_date,
                   flags, body_string, created):
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
    # trickle-down bugs
    assert account is not None and account.namespace is not None
    assert not isinstance(body_string, unicode)

    try:
        parsed = mime.from_string(body_string)

        mime_version = parsed.headers.get('Mime-Version')
        # NOTE: sometimes MIME-Version is set to "1.0 (1.0)", hence the
        # .startswith
        if mime_version is not None and not mime_version.startswith('1.0'):
            log.error('Unexpected MIME-Version: {0}'.format(mime_version))

        new_msg = SpoolMessage() if created else Message()
        new_msg.data_sha256 = sha256(body_string).hexdigest()

        # clean_subject strips re:, fwd: etc.
        new_msg.subject = parsed.clean_subject
        new_msg.from_addr = parse_email_address_list(
            parsed.headers.get('From'))
        new_msg.sender_addr = parse_email_address_list(
            parsed.headers.get('Sender'))
        new_msg.reply_to = parse_email_address_list(
            parsed.headers.get('Reply-To'))

        new_msg.to_addr = parse_email_address_list(parsed.headers.getall('To'))
        new_msg.cc_addr = parse_email_address_list(parsed.headers.getall('Cc'))
        new_msg.bcc_addr = parse_email_address_list(
            parsed.headers.getall('Bcc'))

        new_msg.in_reply_to = parsed.headers.get('In-Reply-To')
        new_msg.message_id_header = parsed.headers.get('Message-Id')

        new_msg.received_date = received_date

        # Optional mailing list headers
        new_msg.mailing_list_headers = parse_ml_headers(parsed.headers)

        # Custom Inbox header
        new_msg.inbox_uid = parsed.headers.get('X-INBOX-ID')
        if created and new_msg.inbox_uid:
            assert isinstance(new_msg, SpoolMessage)
            new_msg.public_id = new_msg.inbox_uid

        # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
        new_msg.references = parse_references(
            parsed.headers.get('References', ''),
            parsed.headers.get('In-Reply-To', ''))

        new_msg.size = len(body_string)  # includes headers text

        i = 0  # for walk_index

        # Store all message headers as object with index 0
        headers_part = Part()
        headers_part.namespace_id = account.namespace.id
        headers_part.message = new_msg
        headers_part.walk_index = i
        headers_part.data = json.dumps(parsed.headers.items())
        new_msg.parts.append(headers_part)

        for mimepart in parsed.walk(
                with_self=parsed.content_type.is_singlepart()):
            i += 1
            if mimepart.content_type.is_multipart():
                log.warning("multipart sub-part found! on {}"
                            .format(new_msg.g_msgid))
                continue  # TODO should we store relations?

            new_part = Part()
            new_part.namespace_id = account.namespace.id
            new_part.message = new_msg
            new_part.walk_index = i
            new_part.misc_keyval = mimepart.headers.items()  # everything
            new_part.content_type = mimepart.content_type.value
            new_part.filename = trim_filename(
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
                        new_part.filename = trim_filename(
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
            new_msg.parts.append(new_part)
    except mime.DecodingError:
        # occasionally iconv will fail via maximum recursion depth
        log_decode_error(account.id, folder_name, mid, body_string)
        log.error('DecodeError, msg logged to {0}'.format(
            get_errfilename(account.id, folder_name, mid)))
        return
    except RuntimeError:
        log_decode_error(account.id, folder_name, mid, body_string)
        log.error('RuntimeError<iconv> msg logged to {0}'.format(
            get_errfilename(account.id, folder_name, mid)))
        return

    new_msg.calculate_sanitized_body()
    return new_msg


def reconcile_message(db_session, log, inbox_uid, new_msg):
    """
    Identify a `Sent Mail` (or corresponding) message synced from the
    remote backend as one we sent and reconcile it with the message we
    created and stored in the local data store at the time of sending.

    Notes
    -----
    Our current reconciliation strategy is to keep both messages i.e.
    the one we sent (SpoolMessage) and the one we synced (Message).

    """
    try:
        spool_message = db_session.query(SpoolMessage).filter(
            SpoolMessage.inbox_uid == inbox_uid).one()
        spool_message.resolved_message = new_msg
        return spool_message

    except NoResultFound:
        log.error('NoResultFound for this message, even though '
                  'it has the inbox-sent header: {0}'.format(inbox_uid))

    except MultipleResultsFound:
        log.error('MultipleResultsFound when reconciling message with '
                  'inbox-sent header: {0}'.format(inbox_uid))
