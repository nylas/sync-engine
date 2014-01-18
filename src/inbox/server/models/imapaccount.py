""" Helper functions for actions that operate on accounts.

These could be methods of ImapAccount, but separating them gives us more
flexibility with calling code, as most don't need any attributes of the
account object other than the ID, to limit the action.
"""
import os
import json

from hashlib import sha256

from sqlalchemy import distinct, func
from sqlalchemy.orm.exc import NoResultFound

from flanker import mime

from inbox.util.misc import or_none
from inbox.util.addr import parse_email_address
from inbox.util.file import mkdirp

from .tables import Block, Message, ImapUid, UIDValidity, FolderItem, Thread

from ..config import config
from ..log import get_logger
log = get_logger()

def total_stored_data(account_id, session):
    """ Computes the total size of the block data of emails in your
        account's IMAP folders
    """
    subq = session.query(Block) \
            .join(Block.message, Message.imapuids) \
            .filter(ImapUid.imapaccount_id==account_id) \
            .group_by(Message.id, Block.id)
    return session.query(func.sum(subq.subquery().columns.size)).scalar()

def total_stored_messages(account_id, session):
    """ Computes the number of emails in your account's IMAP folders """
    return session.query(Message) \
            .join(Message.imapuids) \
            .filter(ImapUid.imapaccount_id==account_id) \
            .group_by(Message.id).count()

def all_uids(account_id, session, folder_name):
    return [uid for uid, in
            session.query(ImapUid.msg_uid).filter_by(
                imapaccount_id=account_id, folder_name=folder_name)]

def g_msgids(account_id, session, in_=None):
    query = session.query(distinct(Message.g_msgid)).join(ImapUid) \
                .filter(ImapUid.imapaccount_id==account_id)
    if in_:
        query = query.filter(Message.g_msgid.in_(in_))
    return sorted([g_msgid for g_msgid, in query], key=long)

def g_metadata(account_id, session, folder_name):
    query = session.query(ImapUid.msg_uid, Message.g_msgid,
                Message.g_thrid).filter(
                        ImapUid.imapaccount_id==account_id,
                        ImapUid.folder_name==folder_name,
                        ImapUid.message_id==Message.id)

    return dict([(int(uid), dict(msgid=g_msgid, thrid=g_thrid)) \
            for uid, g_msgid, g_thrid in query])

def update_metadata(account_id, session, folder_name, uids, new_flags):
    """ Update flags (the only metadata that can change). """
    for item in session.query(ImapUid).filter(
            ImapUid.imapaccount_id==account_id,
            ImapUid.msg_uid.in_(uids),
            ImapUid.folder_name==folder_name):
        flags = new_flags[item.msg_uid]['flags']
        labels = new_flags[item.msg_uid]['labels']
        item.update_flags(flags, labels)

def remove_messages(account_id, session, uids, folder):
    fm_query = session.query(ImapUid).filter(
            ImapUid.imapaccount_id==account_id,
            ImapUid.folder_name==folder,
            ImapUid.msg_uid.in_(uids))
    fm_query.delete(synchronize_session='fetch')

    # XXX TODO: Have a recurring worker permanently remove dangling
    # messages from the database and block store. (Probably too
    # expensive to do here.)

def get_uidvalidity(account_id, session, folder_name):
    try:
        # using .one() here may catch duplication bugs
        return session.query(UIDValidity).filter_by(
                imapaccount_id=account_id, folder_name=folder_name).one()
    except NoResultFound:
        return None

def uidvalidity_valid(account_id, session, selected_uidvalidity, \
        folder_name, cached_uidvalidity=None):
    """ Validate UIDVALIDITY on currently selected folder. """
    if cached_uidvalidity is None:
        cached_uidvalidity = get_uidvalidity(account_id,
                session, folder_name).uid_validity
        assert type(cached_uidvalidity) == type(selected_uidvalidity), \
                "cached_validity: {0} / selected_uidvalidity: {1}".format(
                        type(cached_uidvalidity),
                        type(selected_uidvalidity))

    if cached_uidvalidity is None:
        # no row is basically equivalent to UIDVALIDITY == -inf
        return True
    else:
        return selected_uidvalidity >= cached_uidvalidity

def update_uidvalidity(account_id, session, folder_name, uidvalidity,
        highestmodseq):
    cached_validity = get_uidvalidity(account_id, session, folder_name)
    if cached_validity is None:
        cached_validity = UIDValidity(imapaccount_id=account_id,
                folder_name=folder_name)
    cached_validity.highestmodseq = highestmodseq
    cached_validity.uid_validity = uidvalidity
    session.add(cached_validity)

def create_message(db_session, log, account, folder_name, uid, internaldate,
        flags, body):
    """ Parses message data, creates metadata database entries, and writes mail
        parts to disk.

        Returns the new ImapUid, which links to new Message and Block
        objects through relationships. All new objects are uncommitted.

        Threads are not computed here; you gotta do that separately.

        This is the one function in this file that gets to take an account
        object instead of an account_id, because we need to relate the
        account to ImapUids for versioning to work, since it needs to look
        up the namespace.
    """
    # trickle-down bugs
    assert account is not None and account.namespace is not None
    try:
        parsed = mime.from_string(body)

        mime_version = parsed.headers.get('Mime-Version')
        # NOTE: sometimes MIME-Version is set to "1.0 (1.0)", hence the .startswith
        if mime_version is not None and not mime_version.startswith('1.0'):
            log.error("Unexpected MIME-Version: %s" % mime_version)

        new_msg = Message()
        new_msg.data_sha256 = sha256(body).hexdigest()

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
        new_msg.message_id = parsed.headers.get('Message-Id')

        new_msg.internaldate = internaldate

        # Mailing list headers
        list_archive = parsed.headers.get('List-Archive')
        list_help = parsed.headers.get('List-Help')
        list_id = parsed.headers.get('List-Id')
        list_owner = parsed.headers.get('List-Owner')
        list_post = parsed.headers.get('List-Post')
        list_subscribe = parsed.headers.get('List-Subscribe')
        list_unsubscribe = parsed.headers.get('List-Unsubscribe')

        imapuid = ImapUid(imapaccount=account, folder_name=folder_name,
                msg_uid=uid, message=new_msg)
        imapuid.update_flags(flags)

        new_msg.size = len(body)  # includes headers text

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
            err = open('err.txt', 'w')
            err.write(mimepart.to_string())
            err.close()
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
    Parsed Content-Disposition was: '{3}'""".format(uid, folder_name,
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
        log_decode_error(account.id, folder_name, uid, body)
        log.error("DecodeError encountered, unparseable message logged to {0}" \
                .format(get_errfilename(account.id, folder_name, uid)))
        return
    new_msg.calculate_sanitized_body()

    return imapuid

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

def add_gmail_attrs(db_session, log, new_uid, flags, folder_name, x_gm_thrid,
        x_gm_msgid, x_gm_labels):
    """ Gmail-specific post-create-message bits."""

    new_uid.message.g_msgid = x_gm_msgid
    # NOTE: g_thrid == g_msgid on the first message in the thread :)
    new_uid.message.g_thrid = x_gm_thrid
    new_uid.update_flags(flags, x_gm_labels)

    # NOTE: This code _requires_ autoflush=True, otherwise duplicate
    # threads may attempt to be created and crash.
    thread = new_uid.message.thread = Thread.from_message(db_session,
            new_uid.imapaccount.namespace, new_uid.message)
    # make sure this thread has all the correct labels
    existing_labels = set([l.folder_name.lower() for l in thread.folders])
    # convert things like \Inbox -> Inbox, \Important -> Important
    # also, gmail labels are case-insensitive
    new_labels = set([l.lstrip('\\').lower() for l in x_gm_labels] + \
            [folder_name.lower()])
    # remove labels that have been deleted -- note that the \Sent label is
    # per-message, not per-thread, but since we always work at the thread
    # level, _we_ apply the label to the whole thread. same goes for
    # \Important.
    thread.folders = [l for l in thread.folders if l.folder_name in new_labels \
            or l.folder_name in ('sent', 'important')]
    # add new labels
    for label in new_labels:
        if label.lower() not in existing_labels:
            # creates by association
            item = FolderItem(thread=thread, folder_name=label)
            db_session.add(item)

    return new_uid

def create_gmail_message(db_session, log, account, folder_name, uid,
        internaldate, flags, body, x_gm_thrid, x_gm_msgid, x_gm_labels):
    new_uid = create_message(db_session, log, account, folder_name, uid,
            internaldate, flags, body)
    if new_uid:
        return add_gmail_attrs(db_session, log, new_uid, flags, folder_name,
                x_gm_thrid, x_gm_msgid, x_gm_labels)
