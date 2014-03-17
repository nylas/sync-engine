""" Message-related functions. """

import os
import json

from hashlib import sha256

import iconvcodec
from flanker import mime

from inbox.util.misc import or_none, parse_ml_headers
from inbox.util.addr import parse_email_address
from inbox.util.file import mkdirp

from inbox.server.models.tables.tables import Message, Block

from ..config import config

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
        flags, raw_message):
    """ Parses message data, creates metadata database entries, and writes mail
        parts to disk.

        Returns the new Message, which links to the new Block objects through
        relationships. All new objects are uncommitted.

        Threads are not computed here; you gotta do that separately.

        Parameters
        ----------
        mid : int
            The account backend-specific message identifier; it's only used for
            logging errors.

        raw_message : str
            The full message including headers.
    """
    # trickle-down bugs
    assert account is not None and account.namespace is not None
    try:
        parsed = mime.from_string(raw_message)

        mime_version = parsed.headers.get('Mime-Version')
        # NOTE: sometimes MIME-Version is set to "1.0 (1.0)", hence the .startswith
        if mime_version is not None and not mime_version.startswith('1.0'):
            log.error("Unexpected MIME-Version: %s" % mime_version)

        new_msg = Message()
        new_msg.data_sha256 = sha256(raw_message).hexdigest()

        # clean_subject strips re:, fwd: etc.
        new_msg.subject = parsed.clean_subject
        new_msg.from_addr = parse_email_address(parsed.headers.get('From'))
        new_msg.sender_addr = parse_email_address(parsed.headers.get('Sender'))
        new_msg.reply_to = parse_email_address(parsed.headers.get('Reply-To'))
        new_msg.to_addr = or_none(parsed.headers.getall('To'),
                lambda tos: filter(lambda p: p is not None,
                    [parse_email_address(t) for t in tos]))
        new_msg.cc_addr = or_none(parsed.headers.getall('Cc'),
                lambda ccs: filter(lambda p: p is not None,
                    [parse_email_address(c) for c in ccs]))
        new_msg.bcc_addr = or_none(parsed.headers.getall('Bcc'),
                lambda bccs: filter(lambda p: p is not None,
                    [parse_email_address(c) for c in bccs]))
        new_msg.in_reply_to = parsed.headers.get('In-Reply-To')
        new_msg.message_id_header = parsed.headers.get('Message-Id')

        new_msg.received_date = received_date

        # Optional mailing list headers
        new_msg.mailing_list_headers = parse_ml_headers(parsed.headers)

        new_msg.size = len(raw_message)  # includes headers text

        i = 0  # for walk_index

        # Store all message headers as object with index 0
        headers_part = Block()
        headers_part.message = new_msg
        headers_part.walk_index = i
        headers_part._data = json.dumps(parsed.headers.items())
        headers_part.size = len(headers_part._data)
        headers_part.data_sha256 = sha256(headers_part._data).hexdigest()
        new_msg.parts.append(headers_part)

        for mimepart in parsed.walk(
                with_self=parsed.content_type.is_singlepart()):
            i += 1
            if mimepart.content_type.is_multipart():
                log.warning("multipart sub-part found! on {0}".format(new_msg.g_msgid))
                continue  # TODO should we store relations?

            new_part = Block()
            new_part.message = new_msg
            new_part.walk_index = i
            new_part.misc_keyval = mimepart.headers.items()  # everything
            new_part.content_type = mimepart.content_type.value
            new_part.filename = mimepart.content_type.params.get('name')

            # Content-Disposition attachment; filename="floorplan.gif"
            if mimepart.content_disposition[0] is not None:
                value, params = mimepart.content_disposition
                if value not in ['inline', 'attachment']:
                    errmsg = """
    Unknown Content-Disposition on message {0} found in {1}.
    Bad Content-Disposition was: '{2}'
    Parsed Content-Disposition was: '{3}'""".format(mid, folder_name,
        mimepart.content_disposition)
                    log.error(errmsg)
                    continue
                else:
                    new_part.content_disposition = value
                    if value == 'attachment':
                        new_part.filename = params.get('filename')

            if mimepart.body is None:
                data_to_write = ''
            elif new_part.content_type.startswith('text'):
                data_to_write = mimepart.body.encode('utf-8', 'strict')
            else:
                data_to_write = mimepart.body
            if data_to_write is None:
                data_to_write = ''
            # normalize mac/win/unix newlines
            data_to_write = data_to_write \
                    .replace('\r\n', '\n').replace('\r', '\n')

            new_part.content_id = mimepart.headers.get('Content-Id')

            new_part._data = data_to_write
            new_part.size = len(data_to_write)
            new_part.data_sha256 = sha256(data_to_write).hexdigest()
            new_msg.parts.append(new_part)
    except mime.DecodingError:
        # occasionally iconv will fail via maximum recursion depth
        log_decode_error(account.id, folder_name, mid, raw_message)
        log.error("DecodeError encountered, unparseable message logged to {0}" \
                .format(get_errfilename(account.id, folder_name, mid)))
        return
    except RuntimeError:
        log_decode_error(account.id, folder_name, mid, raw_message)
        log.error("RuntimeError encountered, probably due to iconv. Unparseable message logged to {0}" \
                .format(get_errfilename(account.id, folder_name, mid)))
        return
    new_msg.calculate_sanitized_body()

    return new_msg
