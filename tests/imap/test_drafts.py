import uuid
import os
import pytest
from sqlalchemy.orm.exc import NoResultFound

from tests.data.messages.replyto_message import TEST_MSG
from tests.util.base import action_queue
from tests.util.crispin import crispin_client
from inbox.server.models.tables.base import Block

ACCOUNT_ID = 1
NAMESPACE_ID = 1
THREAD_ID = 16


@pytest.fixture(scope='function')
def message(db, config):
    from inbox.server.models.tables.imap import ImapAccount

    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    to = [{"name": "The red-haired mermaid",
           "email": account.email_address}]
    subject = 'Draft test: ' + str(uuid.uuid4().hex)
    body = '<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>'

    return (to, subject, body)


@pytest.fixture(scope='function')
def attach(db, config):
    test_data = [('muir.jpg', 'image/jpeg'),
                 ('LetMeSendYouEmail.wav', 'audio/vnd.wave'),
                 ('first-attachment.jpg', 'image/jpeg')]

    new_attachments = []
    for _, (test_attachment_filename, ct) in enumerate(test_data):

        test_attachment_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'data', test_attachment_filename)

        with open(test_attachment_path, 'r') as f:
            b = Block(namespace_id=NAMESPACE_ID,
                      filename=test_attachment_filename,
                      data=f.read())
            b.content_type = ct  # for now because of lousy _content_type enum
            db.session.add(b)
            db.session.commit()
            new_attachments.append(b.public_id)

    return new_attachments


@pytest.fixture(autouse=True)
def register_action_backends(db):
    """
    Normally action backends only get registered when the actions
    rqworker starts. So we need to register them explicitly for these
    tests.
    """
    from inbox.server.actions.base import register_backends
    register_backends()


def cleanup(account, subject):
    """ Delete emails in remote. """
    with crispin_client(account.id, account.provider) as c:
        criteria = ['NOT DELETED', 'SUBJECT "{0}"'.format(subject)]

        c.conn.select_folder(account.drafts_folder.name, readonly=False)
        draft_uids = c.conn.search(criteria)
        if draft_uids:
            c.conn.delete_messages(draft_uids)
            c.conn.expunge()

        c.conn.select_folder(account.sent_folder.name, readonly=False)
        sent_uids = c.conn.search(criteria)
        if sent_uids:
            c.conn.delete_messages(sent_uids)
            c.conn.expunge()

        c.conn.select_folder(account.inbox_folder.name, readonly=False)
        inbox_uids = c.conn.search(criteria)
        if inbox_uids:
            c.conn.delete_messages(inbox_uids)
            c.conn.expunge()


def test_get(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import create_draft, get_draft
    from inbox.server.models.tables.base import SpoolMessage, Account

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    created = create_draft(db.session, account, to, subject, body,
                           attachment, cc, bcc)
    public_id = created.public_id

    spoolmessage = db.session.query(SpoolMessage).get(created.id)
    assert spoolmessage, 'draft not in database'

    draft = get_draft(db.session, account, public_id)
    assert draft, 'draft present in database but not returned'

    assert draft.public_id == public_id, \
        'returned draft has incorrect public_id'

    assert draft.state == 'draft', \
        'returned draft has incorrect state'


def test_get_all(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import create_draft, get_all_drafts
    from inbox.server.models.tables.base import Account

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    draft = create_draft(db.session, account, to, subject, body,
                         attachment, cc, bcc)
    public_id = draft.public_id

    new_draft = create_draft(db.session, account, None,
                             'Parent draft', 'Parent draft',
                             None, None)
    new_public_id = new_draft.public_id

    drafts = get_all_drafts(db.session, account)
    assert drafts and len(drafts) == 2, 'drafts not returned'

    first = drafts[0]
    assert first.public_id == public_id or first.public_id == new_public_id, \
        'first draft has incorrect public_id'

    assert first.state == 'draft', \
        'first draft has incorrect state'

    second = drafts[1]
    assert (
        second.public_id == public_id or second.public_id == new_public_id) \
        and (second.public_id != first.public_id), \
        'second draft has incorrect public_id'

    assert first.state == 'draft', \
        'second draft has incorrect state'


def test_create(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import create_draft
    from inbox.server.models.tables.base import (SpoolMessage, FolderItem,
                                                 Folder, Account)

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    created = create_draft(db.session, account, to, subject, body,
                           attachment, cc, bcc)
    public_id = created.public_id

    draft_messages = db.session.query(SpoolMessage).filter(
        SpoolMessage.subject == subject).all()
    assert len(draft_messages) == 1, 'draft message missing'

    draft = draft_messages[0]

    assert draft.public_id == public_id,\
        'draft message has incorrect public_id: expected {0}, got {1}'.format(
            public_id, draft.public_id)

    assert draft.inbox_uid == draft.public_id,\
        'draft message has incorrect inbox_uid: expected {0}, got {1}'.format(
            draft.public_id, draft.inbox_uid)

    draftuid = draft.imapuids[0]
    assert draft.state == 'draft' and draftuid.is_draft,\
        'draft has incorrect state'

    assert draft.is_draft, 'message.is_draft not set to True'

    draft_thrid = draft.thread_id
    draft_folder = db.session.query(Account).get(ACCOUNT_ID).drafts_folder.name
    draft_items = db.session.query(FolderItem).join(Folder).filter(
        FolderItem.thread_id == draft_thrid,
        Folder.name == draft_folder).count()
    assert draft_items == 1, 'draft folder entry missing'

    cleanup(account, subject)


def test_update(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import create_draft, update_draft
    from inbox.server.models.tables.base import Account

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    original_draft = create_draft(db.session, account, None,
                                  'Parent draft', 'Parent draft',
                                  None, None)
    assert original_draft, 'original draft message missing'
    original_id = original_draft.public_id

    # Update a 'valid' draft
    updated_draft = update_draft(db.session, account, original_id, to, subject,
                                 body, attachment, cc, bcc)
    assert updated_draft, 'updated draft message missing'
    updated_id = updated_draft.public_id

    assert original_id != updated_id,\
        'updated draft message has same public_id as original draft'

    assert updated_draft.parent_draft.public_id == original_id,\
        'updated draft has incorrect parent_draft'

    # Update an already-updated draft
    reupdated_draft = update_draft(db.session, account, original_id, to,
                                   subject, body, attachment, cc, bcc)

    assert reupdated_draft.parent_draft.public_id != original_id,\
        'copy of original draft not created'

    assert reupdated_draft.parent_draft.draft_copied_from ==\
        original_draft.id,\
        'copy of original draft has incorrect draft_copied_from id'

    cleanup(account, subject)


def test_delete(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import (create_draft, update_draft,
                                            delete_draft)
    from inbox.server.models.tables.base import SpoolMessage, Account

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    original_draft = create_draft(db.session, account, None,
                                  'Parent draft', 'Parent draft',
                                  None, None)
    assert original_draft, 'original draft message missing'
    original_id = original_draft.public_id

    updated_draft = update_draft(db.session, account, original_id, to, subject,
                                 body, attachment, cc, bcc)
    assert updated_draft, 'updated draft message missing'
    updated_id = updated_draft.public_id

    delete_draft(db.session, account, updated_id)

    with pytest.raises(NoResultFound):
        db.session.query(SpoolMessage).filter_by(
            public_id=updated_id).one()

        db.session.query(SpoolMessage).filter_by(
            public_id=original_id).one()

    new_count = db.session.query(SpoolMessage).filter_by(
        public_id=updated_id).count()
    assert new_count == 0, 'new draft not deleted'

    old_count = db.session.query(SpoolMessage).filter_by(
        public_id=original_id).count()
    assert old_count == 0, 'original draft not deleted'

    cleanup(account, subject)


def test_send(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import create_draft, send_draft
    from inbox.server.models.tables.base import (SpoolMessage, Account,
                                                 FolderItem, Folder)

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    draft = create_draft(db.session, account, to, subject, body,
                         attachment, cc, bcc)

    send_draft(account.id, draft.id)

    # Since the send_draft call uses its own session, we need to start a new
    # session to see its effects.
    db.new_session()

    account = db.session.query(Account).get(ACCOUNT_ID)
    message = db.session.query(SpoolMessage).filter(
        SpoolMessage.public_id == draft.public_id).one()

    # Check sent
    assert message.inbox_uid, 'sent message.inbox_uid missing'

    assert message.is_sent, 'message.is_sent not set to True'

    assert message.imapuids[0].folder.name == account.sent_folder.name, \
        'message.imapuid.folder is not set to sent folder'

    thread = message.thread
    sent_tag = thread.namespace.tags['sent']
    sent_items = sent_tag.tagitems
    assert len(sent_items) == 1, 'sent folder entry missing'

    # Check not-draft
    assert not message.is_draft, 'message.is_draft still set to True'

    draft_thrid = message.thread_id
    draft_folder = db.session.query(Account).get(ACCOUNT_ID).drafts_folder.name
    draft_items = db.session.query(FolderItem).join(Folder).filter(
        FolderItem.thread_id == draft_thrid,
        Folder.name == draft_folder).count()
    # TODO(emfree) fix by only modifying the draft tag (not the folder)
    # locally.
    assert draft_items == 0, 'draft folder entry still present'

    cleanup(account, subject)


def test_create_reply(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import create_draft
    from inbox.server.models.tables.base import (SpoolMessage, Account,
                                                 Message, Thread, DraftThread)

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    thread = db.session.query(Thread).filter(
        Thread.namespace_id == NAMESPACE_ID,
        Thread.id == THREAD_ID).one()
    thread_public_id = thread.public_id
    message_id = thread.messages[0].id
    message_public_id = thread.messages[0].public_id

    draft = create_draft(db.session, account, to, subject, body,
                         attachment, cc, bcc, thread_public_id)
    public_id = draft.public_id

    # Verify draft message creation
    draft_messages = db.session.query(SpoolMessage).\
        filter(SpoolMessage.subject == subject).all()
    assert len(draft_messages) == 1, 'draft message missing'

    draft = draft_messages[0]

    assert draft.public_id == public_id and \
        draft.public_id != message_public_id, \
        'draft message has incorrect public_id'

    draftuid = draft.imapuids[0]
    assert draft.state == 'draft' and draftuid.is_draft,\
        'draft has incorrect state'

    assert draft.replyto_thread_id, 'draft message does not have a draftthread'

    draftthread = db.session.query(DraftThread).get(draft.replyto_thread_id)
    assert draftthread, 'draftthread missing'

    assert draftthread.master_public_id == thread_public_id, \
        'draftthread has incorrect master_public_id'

    assert draftthread.thread_id == THREAD_ID, \
        'draftthread has incorrect thread_id'

    assert draftthread.message_id == message_id, \
        'draftthread has incorrect message_id'

    # Verify original preservation
    messages = db.session.query(Message).\
        filter_by(public_id=message_public_id).all()
    assert len(messages) == 1 and messages[0].discriminator == 'message' and \
        messages[0].id == message_id, 'original message missing'

    original = db.session.query(Thread).filter(
        Thread.namespace_id == NAMESPACE_ID,
        Thread.id == THREAD_ID).one()

    assert original.public_id == thread_public_id, \
        "thread's public_id has changed"

    cleanup(account, subject)


def test_update_reply(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import create_draft, update_draft
    from inbox.server.models.tables.base import Account, Thread, DraftThread

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    thread = db.session.query(Thread).filter(
        Thread.namespace_id == NAMESPACE_ID,
        Thread.id == THREAD_ID).one()
    thread_public_id = thread.public_id

    original_draft = create_draft(db.session, account, to, subject, body,
                                  attachment, cc, bcc, thread_public_id)
    assert original_draft, 'original draft message missing'
    original_id = original_draft.public_id

    # Update a 'valid' draft
    updated_draft = update_draft(db.session, account, original_id, to, subject,
                                 body, attachment, cc, bcc)
    assert updated_draft, 'updated draft message missing'
    updated_id = updated_draft.public_id

    assert original_id != updated_id,\
        'updated draft message has same public_id as original draft'

    assert updated_draft.parent_draft.public_id == original_draft.public_id,\
        'updated draft has incorrect parent_draft'

    assert original_draft.replyto_thread_id == \
        updated_draft.replyto_thread_id, \
        'updated draft has incorrect replyto_thread_id'

    # Update an already-updated draft
    reupdated_draft = update_draft(db.session, account, original_id, to,
                                   subject, body, attachment, cc, bcc)

    assert reupdated_draft.parent_draft.public_id != \
        original_draft.public_id, 'copy of original draft not created'

    assert reupdated_draft.parent_draft.draft_copied_from == \
        original_draft.id, \
        'copy of original draft has incorrect draft_copied_from id'

    assert reupdated_draft.replyto_thread_id != \
        updated_draft.replyto_thread_id, \
        'copy of draftthread not created'

    draftthread = db.session.query(DraftThread).get(
        reupdated_draft.replyto_thread_id)
    assert draftthread, 'copy of draftthread missing'

    thread_copy_1 = updated_draft.replyto_thread
    thread_copy_2 = reupdated_draft.replyto_thread

    assert thread_copy_2.master_public_id == thread_copy_1.master_public_id \
        and thread_copy_2.thread_id == thread_copy_1.thread_id and \
        thread_copy_2.message_id == thread_copy_1.message_id, \
        'copy of draftthread has incorrect references'

    cleanup(account, subject)


@pytest.mark.xfail
def test_delete_reply():
    raise NotImplementedError


def test_send_reply(db, config, action_queue, message, attach):
    from inbox.server.sendmail.base import create_draft, send_draft
    from inbox.server.models.tables.base import (SpoolMessage, Account,
                                                 Thread, FolderItem,
                                                 Folder)

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = attach
    cc = [{'name': 'Ben', 'email': 'ben.bitdiddle1861@gmail.com'}]
    bcc = None

    thread = db.session.query(Thread).filter(
        Thread.namespace_id == NAMESPACE_ID,
        Thread.id == THREAD_ID).one()
    thread_public_id = thread.public_id

    draft = create_draft(db.session, account, to, subject, body, attachment,
                         cc, bcc, thread_public_id)

    send_draft(account.id, draft.id)

    # Since the send_draft call uses its own session, we need to start a new
    # session to see its effects.
    db.new_session()

    account = db.session.query(Account).get(ACCOUNT_ID)
    message = db.session.query(SpoolMessage).filter(
        SpoolMessage.public_id == draft.public_id).one()

    # Check sent
    assert message.is_sent, 'message.is_sent not set to True'

    assert message.imapuids[0].folder.name == account.sent_folder.name, \
        'message.imapuid.folder is not set to sent folder'

    thread = message.thread
    sent_tag = thread.namespace.tags['sent']
    sent_items = sent_tag.tagitems
    assert len(sent_items) == 1, 'sent folder entry missing'

    assert message.inbox_uid, 'sent message.inbox_uid missing'

    expected_in_reply_to = TEST_MSG['message-id']
    in_reply_to = message.in_reply_to
    assert in_reply_to == expected_in_reply_to, 'incorrect in_reply_to header'

    separator = '\t'
    expected_references = TEST_MSG['references'] + separator +\
        TEST_MSG['message-id']
    references = message.references

    assert references.split() == expected_references.split(),\
        'incorrect references header'

    # Check not-draft
    assert not message.is_draft, 'message.is_draft still set to True'

    draft_thrid = message.thread_id
    draft_folder = db.session.query(Account).get(ACCOUNT_ID).drafts_folder.name
    draft_items = db.session.query(FolderItem).join(Folder).filter(
        FolderItem.thread_id == draft_thrid,
        Folder.name == draft_folder).count()
    # TODO(emfree) fix by only modifying the draft tag (not the folder)
    # locally.
    assert draft_items == 0, 'draft folder entry still present'

    cleanup(account, subject)
