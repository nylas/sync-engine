import os, subprocess
import zerorpc

from shutil import rmtree
from pytest import fixture

from inbox.util.db import drop_everything

TEST_CONFIG = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), '..', 'config.cfg')

# Dump file generated using mysqldump
TEST_DATA = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), '..', 'data', 'base_dump.sql')

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

@fixture(scope='session')
def db(request, config):
    """ NOTE: You cannot rely on IMAP UIDs from the test db being correctly
        up-to-date. If you need to test sync functionality, start with a
        test database containing only an authed user, not this dump.
    """
    testdb = TestDB(config)
    request.addfinalizer(testdb.destroy)
    return testdb

class TestDB(object):
    def __init__(self, config):
        from inbox.server.models import new_db_session, init_db, engine
        # Set up test database
        init_db()
        self.session = new_db_session()
        self.engine = engine
        self.config = config

        # Populate with test data
        self.populate()

    def populate(self):
        # Note: Since database is called test, all users have access to it;
        # don't need to read in the username + password from config.
        database = self.config.get('MYSQL_DATABASE')
        dump_filename = TEST_DATA

        cmd = 'mysql {0} < {1}'.format(database, dump_filename)
        subprocess.check_call(cmd, shell=True)

    def destroy(self):
        """ Removes all data from the test database. """
        self.session.close()
        drop_everything(self.engine, with_users=True)

class TestZeroRPC(object):
    """ client/server handle for a ZeroRPC service """
    def __init__(self, config, database, cls, service_loc):
        self.db = database

        from inbox.server.util.concurrency import make_zerorpc

        self.server = make_zerorpc(cls, service_loc)

        self.client = zerorpc.Client(timeout=5)
        self.client.connect(service_loc)
