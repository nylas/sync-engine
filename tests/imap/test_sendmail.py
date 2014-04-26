# XXX can we use mailgun to integrate tests? - have routes that get messages
# delivered back to us.

from pytest import fixture
import magic

from tests.util.api import api_client

USER_ID = 1
ACCOUNT_ID = 1
NAMESPACE_ID = 1


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

    with open(filename, 'rb') as f:
        data = f.read()
        attachfile = dict(filename=filename,
                          data=data,
                          content_type=magic.from_buffer(data, mime=True))

    return [attachfile]


def test_send(db, config, api_client, message, attach):
    from inbox.server.models.tables.base import Message, FolderItem

    recipients, subject, body = message
    attachment = attach

    result = api_client.send_mail(USER_ID, NAMESPACE_ID, recipients, subject,
                                  body, attachment)
    assert result == 'OK', 'send_mail API call failed'

    sent_thrid = db.session.query(Message.thread_id).\
        filter_by(subject=subject).count()

    assert sent_thrid == 1, 'sent message missing'

    sent_items = db.session.query(FolderItem).\
        filter_by(thread_id=sent_thrid, folder_name='sent').count()
    assert sent_items == 1, 'sent folder entry missing'
