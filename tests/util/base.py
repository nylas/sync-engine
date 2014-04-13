import os, subprocess

import zerorpc
from shutil import rmtree
from pytest import fixture

from inbox.util.db import drop_everything
from inbox.util.misc import load_modules

TEST_CONFIG = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), '..', 'config.cfg')


def absolute_path(path):
    """ Returns the absolute path for a path specified as relative to the
        tests/ directory, needed for the dump file name in config.cfg
    """
    return os.path.abspath(\
        os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', path))


@fixture(scope='session', autouse=True)
def config():
    from inbox.server.config import load_config, config
    load_config(filename=TEST_CONFIG)
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


@fixture(scope='function')
def db(request, config):
    """ NOTE: You cannot rely on IMAP UIDs from the test db being correctly
        up-to-date. If you need to test sync functionality, start with a
        test database containing only an authed user, not this dump.
    """
    dumpfile = request.param[0]
    savedb = request.param[1]

    testdb = TestDB(config, dumpfile)

    def save():
        testdb.save()
        testdb.destroy()

    request.addfinalizer(save) if savedb \
        else request.addfinalizer(testdb.destroy)

    return testdb


@fixture(scope='function')
def action_queue(request, config):
    from inbox.server.actions import base
    q = base.get_queue()
    request.addfinalizer(q.empty)
    # make sure it's empty to start out with too
    q.empty()
    return q


class TestDB(object):
    def __init__(self, config, dumpfile):
        from inbox.server.models import new_db_session, engine
        # Set up test database
        self.session = new_db_session()
        self.engine = engine
        self.config = config
        self.dumpfile = dumpfile

        # Populate with test data
        self.populate()

    def populate(self):
        """ Populates database with data from the test dumpfile. """
        # Note: Since database is called test, all users have access to it;
        # don't need to read in the username + password from config.
        database = self.config.get('MYSQL_DATABASE')

        cmd = 'mysql {0} < {1}'.format(database, self.dumpfile)
        subprocess.check_call(cmd, shell=True)

    def new_session(self):
        from inbox.server.models import new_db_session
        self.session.close()
        self.session = new_db_session()

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
    def __init__(self, config, database, cls, service_loc):
        self.db = database

        from inbox.server.util.concurrency import make_zerorpc

        self.server = make_zerorpc(cls, service_loc)

        self.client = zerorpc.Client(timeout=5)
        self.client.connect(service_loc)
