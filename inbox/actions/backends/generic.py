# -*- coding: utf-8 -*-
""" Operations for syncing back local datastore changes to
    generic IMAP providers.
"""
from collections import defaultdict
from nylas.logging import get_logger
from inbox.mailsync.backends.imap.generic import uidvalidity_cb
from inbox.models.backends.imap import ImapUid
from inbox.models import Folder, Category, Account, Message
from inbox.models.session import session_scope
from imaplib import IMAP4
from inbox.sendmail.base import generate_attachments
from inbox.sendmail.message import create_email

log = get_logger()

PROVIDER = 'generic'

__all__ = ['set_remote_starred', 'set_remote_unread', 'remote_move',
           'remote_save_draft', 'remote_delete_draft', 'remote_create_folder',
           'remote_update_folder', 'remote_delete_folder']

# STOPSHIP(emfree):
# * should update local UID state here after action succeeds, instead of
#   waiting for sync to pick it up
# * should add support for rolling back message.categories() on failure.


def uids_by_folder(message_id, db_session):
    results = db_session.query(ImapUid.msg_uid, Folder.name).join(Folder). \
        filter(ImapUid.message_id == message_id).all()
    mapping = defaultdict(list)
    for uid, folder_name in results:
        mapping[folder_name].append(uid)
    return mapping


def _create_email(account, message):
    blocks = [p.block for p in message.attachments]
    attachments = generate_attachments(blocks)
    from_name, from_email = message.from_addr[0]
    msg = create_email(from_name=from_name,
                       from_email=from_email,
                       reply_to=message.reply_to,
                       nylas_uid=message.nylas_uid,
                       to_addr=message.to_addr,
                       cc_addr=message.cc_addr,
                       bcc_addr=message.bcc_addr,
                       subject=message.subject,
                       html=message.body,
                       in_reply_to=message.in_reply_to,
                       references=message.references,
                       attachments=attachments)
    return msg


def _set_flag(crispin_client, account_id, message_id, flag_name,
                          is_add):
    with session_scope(account_id) as db_session:
        uids_for_message = uids_by_folder(message_id, db_session)
    if not uids_for_message:
        log.warning('No UIDs found for message', message_id=message_id)
        return

    for folder_name, uids in uids_for_message.items():
        crispin_client.select_folder_if_necessary(folder_name, uidvalidity_cb)
        if is_add:
            crispin_client.conn.add_flags(uids, [flag_name], silent=True)
        else:
            crispin_client.conn.remove_flags(uids, [flag_name], silent=True)


def set_remote_starred(crispin_client, account, message_id, starred):
    _set_flag(crispin_client, account, message_id, '\\Flagged',
                          starred)


def set_remote_unread(crispin_client, account, message_id, unread):
    _set_flag(crispin_client, account, message_id, '\\Seen',
                          not unread)


def remote_move(crispin_client, account_id, message_id,
                            destination):
    with session_scope(account_id) as db_session:
        uids_for_message = uids_by_folder(message_id, db_session)
    if not uids_for_message:
        log.warning('No UIDs found for message', message_id=message_id)
        return

    for folder_name, uids in uids_for_message.items():
        crispin_client.select_folder_if_necessary(folder_name, uidvalidity_cb)
        crispin_client.conn.copy(uids, destination)
        crispin_client.delete_uids(uids)


def remote_create_folder(crispin_client, account_id, category_id):
    with session_scope(account_id) as db_session:
        category = db_session.query(Category).get(category_id)
        if category is None:
            return
        display_name = category.display_name
    crispin_client.conn.create_folder(display_name)


def remote_update_folder(crispin_client, account_id, category_id, old_name):
    with session_scope(account_id) as db_session:
        category = db_session.query(Category).get(category_id)
        if category is None:
            return
        display_name = category.display_name
    crispin_client.conn.rename_folder(old_name, display_name)


def remote_delete_folder(crispin_client, account_id, category_id):
    with session_scope(account_id) as db_session:
        category = db_session.query(Category).get(category_id)
        if category is None:
            return
        display_name = category.display_name

    try:
        crispin_client.conn.delete_folder(display_name)
    except IMAP4.error:
        # Folder has already been deleted on remote. Treat delete as
        # no-op.
        pass

    with session_scope(account_id) as db_session:
        category = db_session.query(Category).get(category_id)
        db_session.delete(category)
        db_session.commit()


def remote_save_draft(crispin_client, account_id, message_id):
    with session_scope(account_id) as db_session:
        account = db_session.query(Account).get(account_id)
        message = db_session.query(Message).get(message_id)
        mimemsg = _create_email(account, message)

    if 'drafts' not in crispin_client.folder_names():
        log.info('Account has no detected drafts folder; not saving draft',
                 account_id=account_id)
        return
    folder_name = crispin_client.folder_names()['drafts'][0]
    crispin_client.select_folder_if_necessary(folder_name, uidvalidity_cb)
    crispin_client.save_draft(mimemsg)


def remote_update_draft(crispin_client, account_id, message_id,
                                    old_message_id_header):
    with session_scope(account_id) as db_session:
        account = db_session.query(Account).get(account_id)
        message = db_session.query(Message).get(message_id)
        message_id_header = message.message_id_header
        mimemsg = _create_email(account, message)

    # Steps to updating draft:
    # 1. Create the new message, unless it's somehow already there
    # 2. Delete the old message the API user is updating

    if 'drafts' not in crispin_client.folder_names():
        log.warning('Account has no drafts folder. Will not save draft.',
                    account_id=account_id)
        return
    folder_name = crispin_client.folder_names()['drafts'][0]
    crispin_client.select_folder_if_necessary(folder_name, uidvalidity_cb)
    existing_new_draft = crispin_client.find_by_header(
        'Message-Id', message_id_header)
    if not existing_new_draft:
        crispin_client.save_draft(mimemsg)
    else:
        log.info('Draft has been saved, will not create a duplicate.',
                 message_id_header=message_id_header)

    # Check for an older version and delete it. (We can stop once we find
    # one, to reduce the latency of this operation.). Note that the old
    # draft does not always have a message id, in which case we can't
    # replace it.
    if old_message_id_header:
        old_version_deleted = crispin_client.delete_draft(
            old_message_id_header)
        if old_version_deleted:
            log.info('Cleaned up old draft',
                     old_message_id_header=old_message_id_header,
                     message_id_header=message_id_header)


def remote_delete_draft(crispin_client, account_id, nylas_uid,
                        message_id_header):
    if 'drafts' not in crispin_client.folder_names():
        log.warning('Account has no detected drafts folder; not deleting draft',
                    account_id=account_id)
        return
    crispin_client.delete_draft(message_id_header)


def remote_delete_sent(crispin_client, account_id, message_id_header,
                       delete_multiple=False):
    if 'sent' not in crispin_client.folder_names():
        log.warning('Account has no detected sent folder; not deleting message',
                    account_id=account_id)
        return
    crispin_client.delete_sent_message(message_id_header, delete_multiple)


def remote_save_sent(crispin_client, account_id, message_id):
    with session_scope(account_id) as db_session:
        account = db_session.query(Account).get(account_id)
        message = db_session.query(Message).get(message_id)
        if message is None:
            log.info('tried to create nonexistent message',
                     message_id=message_id, account_id=account_id)
            return
        mimemsg = _create_email(account, message)

    if 'sent' not in crispin_client.folder_names():
        log.warning('Account has no detected sent folder; not saving message',
                    account_id=account_id)
        return

    # If there are multiple sent roles we should at least have a warning about it.
    sent_folder_names = crispin_client.folder_names()['sent']
    if len(sent_folder_names) > 1:
        log.warning("Multiple sent folders found for account",
                    account_id=account_id)

    folder_name = sent_folder_names[0]
    crispin_client.select_folder_if_necessary(folder_name, uidvalidity_cb)
    crispin_client.create_message(mimemsg)
