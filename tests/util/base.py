import json
import os
import subprocess
from datetime import datetime, timedelta

from pytest import fixture, yield_fixture


def absolute_path(path):
    """
    Returns the absolute path for a path specified as relative to the
    tests/ directory, needed for the dump file name in config.cfg

    """
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', path))


@fixture(scope='session', autouse=True)
def config():
    from inbox.config import config
    assert 'INBOX_ENV' in os.environ and \
        os.environ['INBOX_ENV'] == 'test', \
        "INBOX_ENV must be 'test' to run tests"
    return config


@fixture(scope='session')
def log(request, config):
    """
    Returns root server logger. For others loggers, use this fixture
    for setup but then call inbox.log.get_logger().

    Testing log file is removed at the end of the test run!

    """
    import logging
    from inbox.util.file import mkdirp
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

    logdir = config.get_required('LOGDIR')
    mkdirp(logdir)
    logfile = config.get_required('TEST_LOGFILE')
    fileHandler = logging.FileHandler(logfile, encoding='utf-8')
    root_logger.addHandler(fileHandler)
    root_logger.setLevel(logging.DEBUG)

    def remove_logs():
        try:
            os.remove(logfile)
        except OSError:
            pass
    request.addfinalizer(remove_logs)


@yield_fixture(scope='function')
def db(request, config):
    """
    NOTE: You cannot rely on IMAP UIDs from the test db being correctly
    up-to-date. If you need to test sync functionality, start with a
    test database containing only an authed user, not this dump.

    """
    dumpfile = request.param[0]
    testdb = TestDB(config, dumpfile)
    yield testdb
    testdb.teardown()


def mock_redis_client(*args, **kwargs):
    return None


@fixture(autouse=True)
def mock_redis(monkeypatch):
    monkeypatch.setattr("inbox.heartbeat.store.HeartbeatStore.__init__",
                        mock_redis_client)


@yield_fixture
def test_client(db):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@yield_fixture
def api_client(db):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield TestAPIClient(c)


class TestAPIClient(object):
    """Provide more convenient access to the API for testing purposes."""
    def __init__(self, test_client):
        self.client = test_client
        self.default_ns_public_id = None

    def full_path(self, path, ns_public_id=None):
        """ Replace a path such as `/tags` by `/n/<ns_public_id>/tags`.

        If no `ns_public_id` is specified, uses the id of the first namespace
        returned by a call to `/n/`.
        """
        if ns_public_id is None:
            if self.default_ns_public_id is None:
                self.default_ns_public_id = ns_public_id = \
                    json.loads(self.client.get('/n/').data)[0]['id']
            else:
                ns_public_id = self.default_ns_public_id

        return '/n/{}'.format(ns_public_id) + path

    def get_raw(self, short_path, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return self.client.get(path)

    def get_data(self, short_path, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return json.loads(self.client.get(path).data)

    def post_data(self, short_path, data, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return self.client.post(path, data=json.dumps(data))

    def post_raw(self, short_path, data, ns_public_id=None, headers=''):
        path = self.full_path(short_path, ns_public_id)
        return self.client.post(path, data=data, headers=headers)

    def put_data(self, short_path, data, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return self.client.put(path, data=json.dumps(data))

    def delete(self, short_path, data=None, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return self.client.delete(path, data=json.dumps(data))


class TestDB(object):
    def __init__(self, config, dumpfile):
        from inbox.models.session import InboxSession
        from inbox.ignition import main_engine
        engine = main_engine()
        # Set up test database
        self.session = InboxSession(engine)
        self.engine = engine
        self.config = config
        self.dumpfile = dumpfile

        # Populate with test data
        self.populate()

    def populate(self):
        """ Populates database with data from the test dumpfile. """
        database = self.config.get('MYSQL_DATABASE')
        user = self.config.get('MYSQL_USER')
        password = self.config.get('MYSQL_PASSWORD')
        hostname = self.config.get('MYSQL_HOSTNAME')
        port = self.config.get('MYSQL_PORT')

        cmd = 'mysql {0} -h{1} -P{2} -u{3} -p{4} < {5}'. \
            format(database, hostname, port, user, password, self.dumpfile)
        subprocess.check_call(cmd, shell=True)

    def teardown(self):
        """
        Closes the session. We need to explicitly do this to prevent certain
        tests from hanging. Note that we don't need to actually destroy or
        rolback the database because we create it anew on each test.

        """
        self.session.close()


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


@yield_fixture(scope='function')
def syncback_service():
    from inbox.transactions.actions import SyncbackService
    s = SyncbackService(poll_interval=0, retry_interval=0)
    s.start()
    yield s
    s.stop()
    s.join()


@fixture(scope='function')
def default_namespace(db):
    from inbox.models import Namespace
    return db.session.query(Namespace).first()


@fixture(scope='function')
def default_account(db):
    import platform
    from inbox.models import Account
    account = db.session.query(Account).filter_by(id=1).one()
    account.create_emailed_events_calendar()
    # Ensure that the account is set to sync locally for unit tests
    account.sync_host = platform.node()
    db.session.commit()
    return account


@fixture(scope='function')
def generic_account(db):
    from inbox.auth.generic import GenericAuthHandler

    handler = GenericAuthHandler(provider_name='generic')
    acc = handler.create_account(db.session, 'user@generic_email.com',
                                 {'email': 'user@genericemail.com',
                                  'password': 'hunter2'})
    db.session.add(acc)
    db.session.commit()
    return acc


@fixture(scope='function')
def contact_sync(config, db):
    from inbox.contacts.remote_sync import ContactSync
    return ContactSync('inboxapptest@gmail.com', 'gmail', 1, 1)


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

    def supply_contact(self, name, email_address, deleted=False):
        from inbox.models import Contact
        self._contacts.append(Contact(namespace_id=1,
                                      uid=str(self._next_uid),
                                      provider_name=self.PROVIDER_NAME,
                                      name=name,
                                      email_address=email_address,
                                      deleted=deleted))
        self._next_uid += 1

    def get_items(self, *args, **kwargs):
        return self._contacts


def add_fake_account(db_session, email_address='test@nilas.com'):
    from inbox.models import Account, Namespace
    namespace = Namespace()
    account = Account(email_address=email_address, namespace=namespace)
    db_session.add(account)
    db_session.commit()
    return account


def add_fake_message(db_session, namespace_id, thread=None, from_addr=None,
                     to_addr=None, cc_addr=None, bcc_addr=None,
                     received_date=None, subject=None):
    from inbox.models import Message
    from inbox.contacts.process_mail import update_contacts_from_message
    m = Message()
    m.namespace_id = namespace_id
    m.from_addr = from_addr or []
    m.to_addr = to_addr or []
    m.cc_addr = cc_addr or []
    m.bcc_addr = bcc_addr or []
    m.received_date = received_date or datetime.utcnow()
    m.size = 0
    m.sanitized_body = ''
    m.snippet = ''
    m.subject = subject or ''

    if thread:
        thread.messages.append(m)
        update_contacts_from_message(db_session, m, thread.namespace)

        db_session.add(m)
        db_session.commit()
    return m


def add_fake_thread(db_session, namespace_id):
    from inbox.models import Thread
    dt = datetime.utcnow()
    thr = Thread(subjectdate=dt, recentdate=dt, namespace_id=namespace_id)
    db_session.add(thr)
    db_session.commit()
    return thr


def add_fake_imapuid(db_session, account_id, message, folder, msg_uid):
    from inbox.models.backends.imap import ImapUid
    imapuid = ImapUid(account_id=account_id,
                      message=message,
                      folder=folder,
                      msg_uid=msg_uid)
    db_session.add(imapuid)
    db_session.commit()
    return imapuid


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


def add_fake_event(db_session, namespace_id):
    from inbox.models import Event
    start = datetime.utcnow()
    end = datetime.utcnow() + timedelta(seconds=1)
    calendar = add_fake_calendar(db_session, namespace_id)
    event = Event(namespace_id=namespace_id,
                  calendar=calendar,
                  title='title',
                  description='',
                  location='',
                  busy=False,
                  read_only=False,
                  reminders='',
                  recurrence='',
                  start=start,
                  end=end,
                  all_day=False,
                  provider_name='inbox',
                  raw_data='',
                  source='local')
    db_session.add(event)
    db_session.commit()
    return event


@fixture
def new_account(db):
    return add_fake_account(db.session)


@fixture
def thread(db, default_namespace):
    return add_fake_thread(db.session, default_namespace.id)


@fixture
def message(db, default_namespace, thread):
    return add_fake_message(db.session, default_namespace.id, thread)


@fixture
def folder(db, default_account):
    from inbox.models.folder import Folder
    return Folder.find_or_create(db.session, default_account,
                                 '[Gmail]/All Mail', 'all')


@fixture
def imapuid(db, default_account, message, folder):
    return add_fake_imapuid(db.session, default_account.id, message,
                            folder, 2222)


@fixture(scope='function')
def calendar(db, default_account):
    return add_fake_calendar(db.session, default_account.namespace.id)
