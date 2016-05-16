from __future__ import division
from flanker import mime

import binascii

from nylas.logging import get_logger
log = get_logger()
from inbox.models import Account
from inbox.models.backends.imap import ImapUid
from inbox.models.session import session_scope
from inbox.util.blockstore import is_in_blockstore, save_to_blockstore
from hashlib import sha256


def _message_missing_s3_object(account_id, folder_id, uid):
    with session_scope(account_id) as db_session:
        acct = db_session.query(Account).get(account_id)

        existing_imapuid = db_session.query(ImapUid).filter(
            ImapUid.account_id == acct.id, ImapUid.folder_id == folder_id,
            ImapUid.msg_uid == uid).first()

        if not existing_imapuid:
            return False

        shas = [part.block.data_sha256 for part in existing_imapuid.message.parts]
        db_session.expunge_all()

    parts_in_blockstore = all(is_in_blockstore(sha) for sha in shas)
    if is_in_blockstore(existing_imapuid.message.data_sha256) and parts_in_blockstore:
        return False

    return True


def _extract_parts(namespace_id, folder_id, body_string):
    data_sha256 = sha256(body_string).hexdigest()

    if not is_in_blockstore(data_sha256):
        save_to_blockstore(data_sha256, body_string)

    try:
        parsed = mime.from_string(body_string)
    except (mime.DecodingError, AttributeError, RuntimeError,
            TypeError) as e:
        log.error('Error parsing message metadata',
                  folder_id=folder_id, namespace_id=namespace_id, error=e)
        return

    if parsed is None:
        return

    for mimepart in parsed.walk(
            with_self=parsed.content_type.is_singlepart()):
        try:
            if mimepart.content_type.is_multipart():
                continue  # TODO should we store relations?
            _parse_mimepart(namespace_id, mimepart)
        except (mime.DecodingError, AttributeError, RuntimeError,
                TypeError, binascii.Error, UnicodeDecodeError) as e:
            log.error('Error parsing message MIME parts',
                      folder_id=folder_id, namespace_id=namespace_id,
                      exc_info=True)
            return


def _parse_mimepart(namespace_id, mimepart):
    disposition, _ = mimepart.content_disposition
    content_id = mimepart.headers.get('Content-Id')
    content_type, params = mimepart.content_type

    filename = mimepart.detected_file_name
    if filename == '':
        filename = None

    data = mimepart.body

    is_text = content_type.startswith('text')

    if disposition not in (None, 'inline', 'attachment'):
        log.error('Unknown Content-Disposition',
                  bad_content_disposition=mimepart.content_disposition)
        return

    if disposition == 'attachment':
        _save_attachment(data)
        return

    if (disposition == 'inline' and
            not (is_text and filename is None and content_id is None)):
        # Some clients set Content-Disposition: inline on text MIME parts
        # that we really want to treat as part of the text body. Don't
        # treat those as attachments.
        _save_attachment(data)
        return

    if is_text:
        if data is None:
            return

        if content_type not in ['text/html', 'text/plain']:
            log.info('Saving other text MIME part as attachment',
                     content_type=content_type, namespace_id=namespace_id)
            _save_attachment(data)
        return

    # Finally, if we get a non-text MIME part without Content-Disposition,
    # treat it as an attachment.
    _save_attachment(data)


def _save_attachment(data):
    if len(data) == 0:
        log.warning('Not saving 0-length data blob')
        return

    if isinstance(data, unicode):
        data = data.encode('utf-8', 'strict')

    data_sha256 = sha256(data).hexdigest()
    save_to_blockstore(data_sha256, data)
