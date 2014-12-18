import json
import os
import subprocess
from datetime import datetime
from gevent import monkey

from pytest import fixture, yield_fixture


def uid():
    from uuid import uuid4
    from struct import unpack
    a, b = unpack('>QQ', uuid4().bytes)
    num = a << 64 | b

    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    base36 = ''
    while num:
        num, i = divmod(num, 36)
        base36 = alphabet[i] + base36

    return base36


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
    savedb = request.param[1]

    testdb = TestDB(config, dumpfile)
    yield testdb

    if savedb:
        testdb.save()
    testdb.teardown()


@yield_fixture
def test_client(db):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# TODO(emfree) can we make this into a yield_fixture without the tests hanging?
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
        self.ns_public_ids = {}

    def full_path(self, path, ns_id=1):
        """
        For testing purposes, replace a path such as '/tags' by
        '/n/<ns_id>/tags', where <ns_id> is the id of the first result of a
        call to '/n/'.

        """
        if ns_id in self.ns_public_ids:
            ns_public_id = self.ns_public_ids[ns_id]
        else:
            # Get the public id corresponding to ns_id and cache it for future
            # use.
            ns_public_id = json.loads(self.client.get('/n/').data)[0]['id']
            self.ns_public_ids[ns_id] = ns_public_id
        return '/n/{}'.format(ns_public_id) + path

    def get_raw(self, short_path, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return self.client.get(path).data

    def get_data(self, short_path, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return json.loads(self.client.get(path).data)

    def post_data(self, short_path, data, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return self.client.post(path, data=json.dumps(data))

    def post_raw(self, short_path, data, ns_id=1, headers=''):
        path = self.full_path(short_path, ns_id)
        return self.client.post(path, data=data, headers=headers)

    def put_data(self, short_path, data, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return self.client.put(path, data=json.dumps(data))

    def delete(self, short_path, data=None, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return self.client.delete(path, data=json.dumps(data))


class TestDB(object):
    def __init__(self, config, dumpfile):
        from inbox.models.session import InboxSession
        from inbox.ignition import main_engine
        engine = main_engine()
        # Set up test database
        self.session = InboxSession(engine, versioned=False)
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

        #Check for env override of host and port
        hostname = self.config.get('MYSQL_HOSTNAME')
        hostname = os.getenv('MYSQL_PORT_3306_TCP_ADDR',hostname)
        port = self.config.get('MYSQL_PORT')
        port = os.getenv('MYSQL_PORT_3306_TCP_PORT',port)

        cmd = 'mysql {0} -h{1} -P{2} -u{3} -p{4} < {5}'.format(database,hostname,port, user, password,
                                                   self.dumpfile)
        subprocess.check_call(cmd, shell=True)

    def new_session(self, ignore_soft_deletes=True):
        from inbox.models.session import InboxSession
        self.session.close()
        self.session = InboxSession(self.engine,
                                    versioned=False,
                                    ignore_soft_deletes=ignore_soft_deletes)

    def teardown(self):
        """
        Closes the session. We need to explicitly do this to prevent certain
        tests from hanging. Note that we don't need to actually destroy or
        rolback the database because we create it anew on each test.

        """
        self.session.rollback()
        self.session.close()

    def save(self):
        """ Updates the test dumpfile. """
        database = self.config.get('MYSQL_DATABASE')

        cmd = 'mysqldump {0} > {1}'.format(database, self.dumpfile)
        subprocess.check_call(cmd, shell=True)


class MockSMTPClient(object):
    def __init__(self, *args, **kwargs):
        pass

    def send_new(self, db_session, draft, recipients):
        # Special mock case to test sending failure handling.
        if 'fail@example.com' in [email for phrase, email in recipients.to]:
            raise Exception
        else:
            pass

    def send_reply(*args, **kwargs):
        pass


@fixture
def patch_network_functions(monkeypatch):
    """
    Monkeypatch functions that actually talk to Gmail so that the tests can
    run faster.

    """
    monkeypatch.setattr('inbox.sendmail.base.get_sendmail_client',
                        lambda *args, **kwargs: MockSMTPClient())
    import inbox.actions
    for backend in inbox.actions.module_registry.values():
        for method_name in backend.__all__:
            monkeypatch.setattr(backend.__name__ + '.' + method_name,
                                lambda *args, **kwargs: None)


@yield_fixture(scope='function')
def syncback_service():
    # aggressive=False used to avoid AttributeError in other tests, see
    # https://groups.google.com/forum/#!topic/gevent/IzWhGQHq7n0
    # TODO(emfree): It's totally whack that monkey-patching here would affect
    # other tests. Can we make this not happen?
    monkey.patch_all(aggressive=False)
    from inbox.transactions.actions import SyncbackService
    s = SyncbackService(poll_interval=0, retry_interval=0)
    s.start()
    yield s
    s.stop()


@fixture(scope='function')
def default_namespace(db):
    from inbox.models import Namespace
    return db.session.query(Namespace).first()


@fixture(scope='function')
def default_account(db):
    import platform
    from inbox.models import Account
    account = db.session.query(Account).filter_by(id=1).one()

    # Ensure that the account is set to sync locally for unit tests
    account.sync_host = platform.node()
    db.session.commit()
    return account


@fixture(scope='function')
def contact_sync(config, db):
    from inbox.contacts.remote_sync import ContactSync
    return ContactSync('gmail', 1, 1)


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
                                      source='remote',
                                      provider_name=self.PROVIDER_NAME,
                                      name=name,
                                      email_address=email_address,
                                      deleted=deleted))
        self._next_uid += 1

    def get_items(self, *args, **kwargs):
        return self._contacts


def add_fake_message(db_session, namespace_id, thread, from_addr=None,
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
    m.thread = thread
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
