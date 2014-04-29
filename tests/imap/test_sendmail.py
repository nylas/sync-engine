# XXX can we use mailgun to integrate tests? - have routes that get messages
# delivered back to us.

from pytest import fixture

from tests.data.messages.replyto_message import TEST_MSG
from tests.util.api import api_client

USER_ID = 1
ACCOUNT_ID = 1
NAMESPACE_ID = 1
THREAD_ID = 6


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


def test_send(db, config, api_client, message, attach):
    from inbox.server.models.tables.base import SpoolMessage, FolderItem

    recipients, subject, body = message
    attachment = attach
    cc = 'ben.bitdiddle1861@gmail.com'
    bcc = None

    result = api_client.send_new(USER_ID, NAMESPACE_ID, recipients, subject,
                                 body, attachment, cc, bcc)
    assert result == 'OK', 'send_mail API call failed'

    sent_messages = db.session.query(SpoolMessage).\
        filter_by(subject=subject).all()
    assert len(sent_messages) == 1, 'sent message missing'

    sent_thrid = sent_messages[0].thread_id
    sent_items = db.session.query(FolderItem).\
        filter_by(thread_id=sent_thrid, folder_name='sent').count()
    assert sent_items == 1, 'sent folder entry missing'


def test_reply(db, config, api_client, message, attach):
    from inbox.server.models.tables.base import SpoolMessage, FolderItem

    recipients, subject, body = message
    attachment = attach

    result = api_client.send_reply(USER_ID, NAMESPACE_ID, THREAD_ID,
                                   recipients, subject, body, attachment)
    assert result == 'OK', 'send_reply API call failed'

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
    sent_items = db.session.query(FolderItem).\
        filter_by(thread_id=sent_thrid, folder_name='sent').all()
    assert len(sent_items) == 1, 'sent folder entry missing'
