import os
import subprocess

import zerorpc
from shutil import rmtree
from pytest import fixture, yield_fixture

from inbox.util.db import drop_everything


def absolute_path(path):
    """ Returns the absolute path for a path specified as relative to the
        tests/ directory, needed for the dump file name in config.cfg
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', path))


@fixture(scope='session', autouse=True)
def config():
    from inbox.server.config import config, load_test_config
    load_test_config()
    return config


@fixture(scope='session')
def log(request, config):
    """ Returns root server logger. For others loggers, use this fixture
        for setup but then call inbox.server.log.get_logger().

        Testing log directory is removed at the end of the test run!
    """
    from inbox.server.log import configure_general_logging

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

    def save():
        testdb.save()
        testdb.destroy()

    testdb = TestDB(config, dumpfile)
    yield testdb

    if savedb:
        testdb.save()
    testdb.destroy()


@fixture(scope='function')
def action_queue(request, config):
    from inbox.server.actions import base
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
    yield app.test_client()


class TestDB(object):
    def __init__(self, config, dumpfile):
        from inbox.server.models import InboxSession
        from inbox.server.models.ignition import engine
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
        from inbox.server.models import InboxSession
        self.session.close()
        self.session = InboxSession(self.engine,
                                    versioned=False,
                                    ignore_soft_deletes=ignore_soft_deletes)

    def destroy(self):
        """ Removes all data from the test database. """
        self.session.close()
        drop_everything(self.engine)

    def save(self):
        """ Updates the test dumpfile. """
        database = self.config.get('MYSQL_DATABASE')

        cmd = 'mysqldump {0} > {1}'.format(database, self.dumpfile)
        subprocess.check_call(cmd, shell=True)


class TestZeroRPC(object):
    """ client/server handle for a ZeroRPC service """
    def __init__(self, config, cls, service_loc):

        from inbox.server.util.concurrency import make_zerorpc

        self.server = make_zerorpc(cls, service_loc)

        self.client = zerorpc.Client(timeout=120)
        self.client.connect(service_loc)
