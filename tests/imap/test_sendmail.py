# XXX can we use mailgun to integrate tests? - have routes that get messages
# delivered back to us.
"""
These tests verify the state of the local data store -
they use the sendmail API calls (send, reply) and verify that the right
SpoolMessage records are created in the database.

They do not test syncback to the remote backend or reconciliation on a
subsequent sync, see tests/imap/network for those.

"""
from pytest import fixture
from inbox.server.sendmail.base import (send, reply, recipients,
                                        create_attachment_metadata)

from tests.data.messages.replyto_message import TEST_MSG

ACCOUNT_ID = 1
NAMESPACE_ID = 1
THREAD_ID = 16


@fixture(scope='function')
def message(db, config):
    from inbox.server.models.tables.imap import ImapAccount

    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    recipients = u'"\u2605The red-haired mermaid\u2605" <{0}>'.\
        format(account.email_address)
    subject = unicode('\xc3\xa4\xc3\xb6\xc3\xbcWakeup', 'utf-8')
    body = '<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>'

    return (recipients, subject, body)


@fixture(scope='function')
def attach(config):
    filename = config.get('ATTACHMENT')
    return [filename]


def test_send(db, config, message, attach):
    from inbox.server.models.tables.base import (SpoolMessage, FolderItem,
                                                 Folder, Account)

    to, subject, body = message
    cc = 'ben.bitdiddle1861@gmail.com'
    bcc = None
    attachfiles = create_attachment_metadata(attach)

    account = db.session.query(Account).get(ACCOUNT_ID)
    send(account, recipients(to, cc, bcc), subject, body, attachfiles)

    sent_messages = db.session.query(SpoolMessage).\
        filter_by(subject=subject).all()
    assert len(sent_messages) == 1, 'sent message missing'

    sent_thrid = sent_messages[0].thread_id

    sent_folder = db.session.query(Account).get(ACCOUNT_ID).sent_folder.name
    sent_items = db.session.query(FolderItem).join(Folder).filter(
        FolderItem.thread_id == sent_thrid,
        Folder.name == sent_folder).count()
    assert sent_items == 1, 'sent folder entry missing'


def test_reply(db, config, message, attach):
    from inbox.server.models.tables.base import (SpoolMessage, FolderItem,
                                                 Folder, Account)

    to, subject, body = message
    attachfiles = create_attachment_metadata(attach)

    account = db.session.query(Account).get(ACCOUNT_ID)
    reply(NAMESPACE_ID, account, THREAD_ID, recipients(to, None, None),
          subject, body, attachfiles)

    sent_messages = db.session.query(SpoolMessage).\
        filter_by(thread_id=THREAD_ID).all()
    assert len(sent_messages) == 1, 'sent message missing'

    expected_in_reply_to = TEST_MSG['message-id']
    in_reply_to = sent_messages[0].in_reply_to
    assert in_reply_to == expected_in_reply_to, 'incorrect in_reply_to header'

    separator = '\t'
    expected_references = TEST_MSG['references'] + separator +\
        TEST_MSG['message-id']
    references = sent_messages[0].references

    assert references.split() == expected_references.split(),\
        'incorrect references header'

    sent_thrid = sent_messages[0].thread_id
    sent_folder = db.session.query(Account).get(ACCOUNT_ID).sent_folder.name
    sent_items = db.session.query(FolderItem).join(Folder).filter(
        FolderItem.thread_id == sent_thrid,
        Folder.name == sent_folder).count()
    assert sent_items == 1, 'sent folder entry missing'
