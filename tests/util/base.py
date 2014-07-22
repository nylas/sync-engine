import json
import os
import sys
import subprocess

import zerorpc
from pytest import fixture, yield_fixture
import gevent


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

    filename = absolute_path('config-test.json')
    try:
        f = open(filename)
    except IOError:
        sys.exit('Missing test config at {0}'.format(filename))
    else:
        with f:
            test_config = json.load(f)
            config.update(test_config)
            if not config.get('MYSQL_HOSTNAME') == 'localhost':
                sys.exit('Tests should only be run on localhost DB!')

    return config


@fixture(scope='session')
def log(request, config):
    """
    Returns root server logger. For others loggers, use this fixture
    for setup but then call inbox.log.get_logger().

    Testing log file is removed at the end of the test run!

    """
    import logging
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

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
    """ NOTE: You cannot rely on IMAP UIDs from the test db being correctly
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

    def full_path(self, path, ns_id):
        """For testing purposes, replace a path such as '/tags' by
        '/n/<ns_id>/tags', where <ns_id> is the id of the first result of a
        call to '/n/'."""
        if ns_id in self.ns_public_ids:
            ns_public_id = self.ns_public_ids[ns_id]
        else:
            # Get the public id corresponding to ns_id and cache it for future
            # use.
            ns_public_id = json.loads(self.client.get('/n/').data)[0]['id']
            self.ns_public_ids[ns_id] = ns_public_id
        return '/n/{}'.format(ns_public_id) + path

    def get_data(self, short_path, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return json.loads(self.client.get(path).data)

    def post_data(self, short_path, data, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return self.client.post(path, data=json.dumps(data))

    def put_data(self, short_path, data, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return self.client.put(path, data=json.dumps(data))

    def delete(self, short_path, ns_id=1):
        path = self.full_path(short_path, ns_id)
        return self.client.delete(path)


class TestDB(object):
    def __init__(self, config, dumpfile):
        from inbox.models.session import InboxSession
        from inbox.ignition import engine
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

        cmd = 'mysql {0} -u{1} -p{2} < {3}'.format(database, user, password,
                                                   self.dumpfile)
        subprocess.check_call(cmd, shell=True)

    def new_session(self, ignore_soft_deletes=True):
        from inbox.models.session import InboxSession
        self.session.close()
        self.session = InboxSession(self.engine,
                                    versioned=False,
                                    ignore_soft_deletes=ignore_soft_deletes)

    def teardown(self):
        """Closes the session. We need to explicitly do this to prevent certain
        tests from hanging. Note that we don't need to actually destroy or
        rolback the database because we create it anew on each test."""
        self.session.close()

    def save(self):
        """ Updates the test dumpfile. """
        database = self.config.get('MYSQL_DATABASE')

        cmd = 'mysqldump {0} > {1}'.format(database, self.dumpfile)
        subprocess.check_call(cmd, shell=True)


class TestZeroRPC(object):
    """ Client/server handle for a ZeroRPC service """
    def __init__(self, config, cls, service_loc):
        from inbox.util.concurrency import make_zerorpc

        self.server = make_zerorpc(cls, service_loc)

        self.client = zerorpc.Client(timeout=120)
        self.client.connect(service_loc)


def kill_greenlets():
    """Utility function to kill all running greenlets."""
    import gc
    for obj in gc.get_objects():
        if isinstance(obj, gevent.Greenlet):
            obj.kill()


class MockSMTPClient(object):
    def __init__(self, *args, **kwargs):
        pass

    def send_new(*args, **kwargs):
        pass

    def send_reply(*args, **kwargs):
        pass


@fixture
def patch_network_functions(monkeypatch):
    """Monkeypatch functions that actually talk to Gmail so that the tests can
    run faster."""
    monkeypatch.setattr('inbox.sendmail.base.get_sendmail_client',
                        lambda *args, **kwargs: MockSMTPClient())
    for func_name in ['mark_read', 'mark_unread', 'archive', 'unarchive',
                      'star', 'unstar', 'save_draft', 'delete_draft',
                      'mark_spam', 'unmark_spam', 'mark_trash',
                      'unmark_trash']:
        monkeypatch.setattr('inbox.actions.' + func_name,
                            lambda *args, **kwargs: None)


@yield_fixture(scope='function')
def syncback_service():
    from inbox.transactions.actions import SyncbackService
    from gevent import monkey
    # aggressive=False used to avoid AttributeError in other tests, see
    # https://groups.google.com/forum/#!topic/gevent/IzWhGQHq7n0
    # TODO(emfree): It's totally whack that monkey-patching here would affect
    # other tests. Can we make this not happen?
    monkey.patch_all(aggressive=False)
    s = SyncbackService(poll_interval=1)
    s.start()
    gevent.sleep()
    yield s
    kill_greenlets()
