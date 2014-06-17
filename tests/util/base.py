import json
import os
import sys
import subprocess

import zerorpc
from shutil import rmtree
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

    Testing log directory is removed at the end of the test run!

    """
    from inbox.log import configure_general_logging

    def remove_logs():
        rmtree(config['LOGDIR'], ignore_errors=True)
    request.addfinalizer(remove_logs)
    return configure_general_logging()


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


@fixture(scope='function')
def action_queue(request, config):
    from inbox.actions import base
    q = base.get_queue()
    request.addfinalizer(q.empty)
    # make sure it's empty to start out with too
    q.empty()
    return q


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
