import json
import mock
import os
import uuid
from datetime import datetime, timedelta

from pytest import fixture, yield_fixture
from flanker import mime
from mockredis import mock_strict_redis_client

from inbox.util.testutils import setup_test_db, MockIMAPClient  # noqa


def absolute_path(path):
    """
    Returns the absolute path for a path specified as relative to the
    tests/ directory, needed for the dump file name in config.cfg

    """
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', path))


def make_config(tmpdir_factory):
    from inbox.config import config
    assert 'NYLAS_ENV' in os.environ and \
        os.environ['NYLAS_ENV'] == 'test', \
        "NYLAS_ENV must be 'test' to run tests"
    # don't try to write test data to the module tree
    config['MSG_PARTS_DIRECTORY'] = str(tmpdir_factory.mktemp("parts"))
    return config


@fixture(scope='session', autouse=True)
def config(tmpdir_factory):
    return make_config(tmpdir_factory)


@fixture(scope='session')
def dbloader(config):
    setup_test_db()


@yield_fixture(scope='function')
def db(dbloader):
    from inbox.ignition import engine_manager
    from inbox.models.session import new_session
    engine = engine_manager.get_for_id(0)
    # TODO(emfree): tests should really either instantiate their own sessions,
    # or take a fixture that is itself a session.
    engine.session = new_session(engine)
    yield engine
    engine.session.close()


@yield_fixture(scope='function')
def empty_db(config):
    from inbox.ignition import engine_manager
    from inbox.models.session import new_session
    setup_test_db()
    engine = engine_manager.get_for_id(0)
    engine.session = new_session(engine)
    yield engine
    engine.session.close()


@yield_fixture
def test_client(db):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@yield_fixture
def webhooks_client(db):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield TestWebhooksClient(c)


class TestWebhooksClient(object):

    def __init__(self, test_client):
        self.client = test_client

    def post_data(self, path, data, headers={}):
        path = '/w' + path
        return self.client.post(path, data=json.dumps(data), headers=headers)


@fixture
def patch_network_functions(monkeypatch):
    """
    Monkeypatch syncback functions that actually talk to Gmail so that the
    tests can run faster.

    """
    import inbox.actions.backends
    for backend in inbox.actions.backends.module_registry.values():
        for method_name in backend.__all__:
            monkeypatch.setattr(backend.__name__ + '.' + method_name,
                                lambda *args, **kwargs: None)


def make_default_account(db, config):
    import platform
    from inbox.models.backends.gmail import GmailAccount
    from inbox.models.backends.gmail import GmailAuthCredentials
    from inbox.auth.gmail import OAUTH_SCOPE
    from inbox.models import Namespace

    ns = Namespace()
    account = GmailAccount(
        sync_host='{}:{}'.format(platform.node(), 0),
        email_address='inboxapptest@gmail.com')
    account.namespace = ns
    account.create_emailed_events_calendar()
    account.refresh_token = 'faketoken'

    auth_creds = GmailAuthCredentials()
    auth_creds.client_id = config.get_required('GOOGLE_OAUTH_CLIENT_ID')
    auth_creds.client_secret = \
        config.get_required('GOOGLE_OAUTH_CLIENT_SECRET')
    auth_creds.refresh_token = 'faketoken'
    auth_creds.g_id_token = 'foo'
    auth_creds.created_at = datetime.utcnow()
    auth_creds.updated_at = datetime.utcnow()
    auth_creds.gmailaccount = account
    auth_creds.scopes = OAUTH_SCOPE

    db.session.add(account)
    db.session.add(auth_creds)
    db.session.commit()
    return account


def delete_default_accounts(db):
    from inbox.models.backends.gmail import GmailAccount
    from inbox.models.backends.gmail import GmailAuthCredentials
    from inbox.models import Namespace
    delete_messages(db.session)
    db.session.rollback()
    db.session.query(GmailAccount).delete()
    db.session.query(GmailAuthCredentials).delete()
    db.session.query(Namespace).delete()
    db.session.commit()


@yield_fixture(scope='function')
def default_account(db, config, redis_mock):
    yield make_default_account(db, config)
    delete_default_accounts(db)


@yield_fixture(scope='function')
def default_namespace(db, default_account):
    yield default_account.namespace


@yield_fixture(scope='function')
def default_accounts(db, config, redis_mock):
    yield [make_default_account(db, config) for _ in range(3)]
    delete_default_accounts(db)


@yield_fixture(scope='function')
def default_namespaces(db, default_accounts):
    yield [account.namespace for account in default_accounts]


@yield_fixture(scope='function')
def generic_account(db):
    yield add_generic_imap_account(db.session)


@yield_fixture(scope='function')
def gmail_account(db):
    yield add_fake_gmail_account(db.session,
                                 email_address='almondsunshine',
                                 refresh_token='tearsofgold',
                                 password='COyPtHmj9E9bvGdN')
    delete_gmail_accounts(db.session)


@fixture(scope='function')
def contact_sync(config, db, default_account):
    from inbox.contacts.remote_sync import ContactSync
    return ContactSync('inboxapptest@gmail.com', 'gmail', default_account.id,
                       default_account.namespace.id)


@fixture(scope='function')
def contacts_provider(config, db):
    return ContactsProviderStub()


class ContactsProviderStub(object):
    """
    Contacts provider stub to stand in for an actual provider.
    When an instance's get_items() method is called, return an iterable of
    Contact objects corresponding to the data it's been fed via
    supply_contact().

    """

    def __init__(self, provider_name='test_provider'):
        self._contacts = []
        self._next_uid = 1
        self.PROVIDER_NAME = provider_name
        self._get_next_uid = lambda current: current + 1

    def supply_contact(self, name, email_address, deleted=False):
        from inbox.models import Contact
        self._contacts.append(Contact(namespace_id=1,
                                      uid=str(self._next_uid),
                                      provider_name=self.PROVIDER_NAME,
                                      name=name,
                                      email_address=email_address,
                                      deleted=deleted))
        self._next_uid = self._get_next_uid(self._next_uid)

    def get_items(self, *args, **kwargs):
        return self._contacts


def add_fake_folder(db_session, default_account, display_name='All Mail',
                    name='all'):
    from inbox.models.folder import Folder
    return Folder.find_or_create(db_session, default_account, display_name, name)


def add_fake_label(db_session, default_account, display_name='My Label',
                    name=None):
    from inbox.models.label import Label
    return Label.find_or_create(db_session, default_account, display_name, name)


def add_generic_imap_account(db_session, email_address='test@nylas.com'):
    import platform
    from inbox.models.backends.generic import GenericAccount
    from inbox.models import Namespace
    account = GenericAccount(email_address=email_address,
                             sync_host=platform.node(),
                             provider='custom')
    account.imap_endpoint = ('imap.custom.com', 993)
    account.smtp_endpoint = ('smtp.custom.com', 587)
    account.imap_password = 'bananagrams'
    account.smtp_password = 'bananagrams'
    account.namespace = Namespace()
    db_session.add(account)
    db_session.commit()
    return account


def delete_generic_imap_accounts(db_session):
    from inbox.models.backends.generic import GenericAccount
    from inbox.models import Namespace
    db_session.rollback()
    db_session.query(GenericAccount).delete()
    db_session.query(Namespace).delete()
    db_session.commit()


def add_fake_yahoo_account(db_session, email_address='cypresstest@yahoo.com'):
    import platform
    from inbox.models.backends.generic import GenericAccount
    from inbox.models import Namespace
    account = GenericAccount(email_address=email_address,
                             sync_host=platform.node(),
                             provider='yahoo')
    account.imap_password = 'bananagrams'
    account.smtp_password = 'bananagrams'
    account.namespace = Namespace()
    db_session.add(account)
    db_session.commit()
    return account


def add_fake_gmail_account(db_session, email_address='test@nilas.com',
                           refresh_token='tearsofgold',
                           password='COyPtHmj9E9bvGdN'):
    from inbox.models import Namespace
    from inbox.models.backends.gmail import GmailAccount
    import platform

    with db_session.no_autoflush:
        namespace = Namespace()

        account = GmailAccount(
            email_address=email_address,
            refresh_token=refresh_token,
            sync_host=platform.node(),
            namespace=namespace)
        account.password = password

        db_session.add(account)
        db_session.commit()
        return account


def delete_gmail_accounts(db_session):
    from inbox.models import Namespace
    from inbox.models.backends.gmail import GmailAccount
    db_session.rollback()
    db_session.query(GmailAccount).delete()
    db_session.query(Namespace).delete()
    db_session.commit()


def add_fake_message(db_session, namespace_id, thread=None, from_addr=None,
                     to_addr=None, cc_addr=None, bcc_addr=None,
                     received_date=None, subject='',
                     body='', snippet='', g_msgid=None,
                     add_sent_category=False):
    from inbox.models import Message, Category
    from inbox.contacts.process_mail import update_contacts_from_message
    m = Message()
    m.namespace_id = namespace_id
    m.from_addr = from_addr or []
    m.to_addr = to_addr or []
    m.cc_addr = cc_addr or []
    m.bcc_addr = bcc_addr or []
    m.received_date = received_date or datetime.utcnow()
    m.size = 0
    m.is_read = False
    m.is_starred = False
    m.body = body
    m.snippet = snippet
    m.subject = subject
    m.g_msgid = g_msgid

    if thread:
        thread.messages.append(m)
        update_contacts_from_message(db_session, m, thread.namespace)

        db_session.add(m)
        db_session.commit()

    if add_sent_category:
        category = Category.find_or_create(
            db_session, namespace_id, 'sent', 'sent', type_='folder')
        if category not in m.categories:
            m.categories.add(category)
        db_session.commit()

    return m


def delete_messages(db_session):
    from inbox.models import Message
    db_session.rollback()
    db_session.query(Message).update({'reply_to_message_id': None})
    db_session.query(Message).delete()
    db_session.commit()


def delete_categories(db_session):
    from inbox.models import Category
    db_session.rollback()
    db_session.query(Category).delete()
    db_session.commit()


def add_fake_thread(db_session, namespace_id):
    from inbox.models import Thread
    dt = datetime.utcnow()
    thr = Thread(subjectdate=dt, recentdate=dt, namespace_id=namespace_id)
    db_session.add(thr)
    db_session.commit()
    return thr


def delete_threads(db_session):
    from inbox.models import Thread
    delete_messages(db_session)
    db_session.rollback()
    db_session.query(Thread).delete()
    db_session.commit()


def add_fake_imapuid(db_session, account_id, message, folder, msg_uid):
    from inbox.models.backends.imap import ImapUid
    imapuid = ImapUid(account_id=account_id,
                      message=message,
                      folder=folder,
                      msg_uid=msg_uid)
    db_session.add(imapuid)
    db_session.commit()
    return imapuid


def delete_imapuids(db_session):
    from inbox.models.backends.imap import ImapUid
    db_session.rollback()
    db_session.query(ImapUid).delete()
    db_session.commit()


def add_fake_calendar(db_session, namespace_id, name="Cal",
                      description="A Calendar", uid="UID", read_only=False):
    from inbox.models import Calendar
    calendar = Calendar(namespace_id=namespace_id,
                        name=name,
                        description=description,
                        uid=uid,
                        read_only=read_only)
    db_session.add(calendar)
    db_session.commit()
    return calendar


def delete_calendars(db_session):
    from inbox.models import Calendar
    db_session.rollback()
    db_session.query(Calendar).delete()
    db_session.commit()


def add_fake_event(db_session, namespace_id, calendar=None,
                   title='title', description='', location='',
                   busy=False, read_only=False, reminders='', recurrence='',
                   start=None, end=None, all_day=False):
    from inbox.models import Event
    start = start or datetime.utcnow()
    end = end or (datetime.utcnow() + timedelta(seconds=1))
    calendar = calendar or add_fake_calendar(db_session, namespace_id)
    event = Event(namespace_id=namespace_id,
                  calendar=calendar,
                  title=title,
                  description=description,
                  location=location,
                  busy=busy,
                  read_only=read_only,
                  reminders=reminders,
                  recurrence=recurrence,
                  start=start,
                  end=end,
                  all_day=all_day,
                  raw_data='',
                  uid=str(uuid.uuid4()))
    event.sequence_number = 0
    db_session.add(event)
    db_session.commit()
    return event


def delete_events(db_session):
    from inbox.models import Event
    db_session.rollback()
    db_session.query(Event).delete()
    db_session.commit()


def add_fake_contact(db_session, namespace_id, name='Ben Bitdiddle',
                     email_address='inboxapptest@gmail.com', uid='22'):
    from inbox.models import Contact
    contact = Contact(namespace_id=namespace_id,
                      name=name,
                      email_address=email_address,
                      uid=uid)

    db_session.add(contact)
    db_session.commit()
    return contact


def delete_contacts(db_session):
    from inbox.models import Contact
    db_session.rollback()
    db_session.query(Contact).delete()
    db_session.commit()


def add_fake_category(db_session, namespace_id, display_name, name=None):
    from inbox.models import Category
    category = Category(namespace_id=namespace_id,
                        display_name=display_name,
                        name=name)
    db_session.add(category)
    db_session.commit()
    return category


@yield_fixture
def thread(db, default_namespace):
    yield add_fake_thread(db.session, default_namespace.id)
    delete_threads(db.session)


@yield_fixture
def message(db, default_namespace, thread):
    yield add_fake_message(db.session, default_namespace.id, thread)
    delete_messages(db.session)


@fixture
def folder(db, default_account):
    from inbox.models.folder import Folder
    return Folder.find_or_create(db.session, default_account,
                                 '[Gmail]/All Mail', 'all')


@fixture
def label(db, default_account):
    from inbox.models import Label
    return Label.find_or_create(db.session, default_account,
                                'Inbox', 'inbox')


@fixture
def custom_label(db, default_account):
    from inbox.models import Label
    return Label.find_or_create(db.session, default_account,
                                'Kraftwerk', '')


@yield_fixture
def contact(db, default_account):
    yield add_fake_contact(db.session, default_account.namespace.id)
    delete_contacts(db.session)


@yield_fixture
def imapuid(db, default_account, message, folder):
    yield add_fake_imapuid(db.session, default_account.id, message,
                            folder, 2222)
    delete_imapuids(db.session)


@yield_fixture(scope='function')
def calendar(db, default_account):
    yield add_fake_calendar(db.session, default_account.namespace.id)
    delete_calendars(db.session)


@yield_fixture(scope='function')
def other_calendar(db, default_account):
    yield add_fake_calendar(db.session, default_account.namespace.id,
                             uid='uid2', name='Calendar 2')
    delete_calendars(db.session)


@yield_fixture(scope='function')
def event(db, default_account):
    yield add_fake_event(db.session, default_account.namespace.id)
    delete_events(db.session)
    delete_calendars(db.session)


@yield_fixture(scope='function')
def imported_event(db, default_account, message):
    ev = add_fake_event(db.session, default_account.namespace.id)
    ev.message = message
    message.from_addr = [['Mick Taylor', 'mick@example.com']]
    ev.owner = 'Mick Taylor <mick@example.com>'
    ev.participants = [{"email": "inboxapptest@gmail.com",
                        "name": "Inbox Apptest", "status": "noreply"}]
    db.session.commit()
    yield ev
    delete_events(db.session)
    delete_calendars(db.session)


@fixture
def mime_message():
    msg = mime.create.multipart('alternative')
    msg.append(
        mime.create.text('plain', 'Hello World!'),
        mime.create.text('html', '<html>Hello World!</html>')
    )
    msg.headers['To'] = 'Alice <alice@example.com>'
    msg.headers['Cc'] = 'Bob <bob@example.com>'
    msg.headers['Subject'] = 'Hello'
    return msg


@fixture
def new_message_from_synced(db, default_account, mime_message):
    from inbox.models import Message
    received_date = datetime(2014, 9, 22, 17, 25, 46)
    new_msg = Message.create_from_synced(default_account,
                                         139219,
                                         '[Gmail]/All Mail',
                                         received_date,
                                         mime_message.to_string())
    assert new_msg.received_date == received_date
    new_msg.is_read = True
    new_msg.is_starred = False
    return new_msg


def add_fake_msg_with_calendar_part(db_session, account, ics_str, thread=None):
    from inbox.models import Message
    parsed = mime.create.multipart('mixed')
    parsed.append(
        mime.create.attachment('text/calendar',
                               ics_str,
                               disposition=None)
    )
    msg = Message.create_from_synced(
        account, 22, '[Gmail]/All Mail', datetime.utcnow(), parsed.to_string())
    msg.from_addr = [('Ben Bitdiddle', 'ben@inboxapp.com')]

    if thread is None:
        msg.thread = add_fake_thread(db_session, account.namespace.id)
    else:
        msg.thread = thread

    assert msg.has_attached_events
    return msg


@yield_fixture
def mock_gevent_sleep(monkeypatch):
    monkeypatch.setattr('gevent.sleep', mock.Mock())
    yield
    monkeypatch.undo()


def mock_client():
    mock_client = mock_strict_redis_client()

    # Adding a couple of methods we use that mockredis doesn't support yet.
    def scan_iter_patch(match=None, count=100):
        match = str(match).replace('*', '')
        return filter(lambda k: k.startswith(match), mock_client.keys())

    mock_client.scan_iter = scan_iter_patch
    mock_client.reset = lambda: True

    def zscan_iter_patch(key, match=None):
        match = str(match).replace('*', '')
        return filter(lambda k: k.startswith(match),
                      mock_client.zrange(key, 0, -1))
    mock_client.zscan_iter = zscan_iter_patch
    return mock_client


@yield_fixture(scope='function')
def redis_client(monkeypatch):
    client = mock_client()
    yield client
    # Flush on teardown
    client.flushdb()


@yield_fixture(scope='function', autouse=True)
def redis_mock(redis_client, monkeypatch):
    def set_self_client(self, *args, **kwargs):
        # Ensure the same 'redis' client is returned across HeartbeatStore
        # calls and direct checks. Mocking StrictRedis() directly causes
        # different clients to be initialized, so we can't check contents.
        self.host = None
        self.port = 6379

    def fake_redis_client(host=None, port=6379, db=1):
        return redis_client

    monkeypatch.setattr("inbox.heartbeat.config.get_redis_client",
                        fake_redis_client)
    monkeypatch.setattr("inbox.heartbeat.store.HeartbeatStore.__init__",
                        set_self_client)
    monkeypatch.setattr('inbox.scheduling.event_queue._get_redis_client',
                        fake_redis_client)
    monkeypatch.setattr('inbox.mailsync.service.SHARED_SYNC_EVENT_QUEUE_ZONE_MAP', {})
    yield
    monkeypatch.undo()
