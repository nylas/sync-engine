import pytest, os, subprocess

TEST_DATA = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'dump.sql')
TEST_CONFIG = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'config.cfg')

@pytest.fixture(scope='session', autouse=True)
def config():
    from inbox.server.config import load_config
    from inbox.server.config import config as confdict
    load_config(filename=TEST_CONFIG)

class TestDB(object):
    def __init__(self):
        from inbox.server.models import new_db_session, init_db, engine
        # Set up test database
        init_db()
        self.db_session = new_db_session()
        self.engine = engine

        # Populate with test data
        self.populate()

    def populate(self):
        # Note: Since database is called test, all users have access to it;
        # don't need to read in the username + password from config.

        # TODO: Don't hardcode, get from config
        database = 'test'
        source = TEST_DATA

        # TODO: Don't hardcode, use database + source vars
        cmd = 'mysql test < /vagrant/tests/dump.sql'
        subprocess.call(cmd, shell=True)

        print 'populate done!'

    def destroy(self):
        from inbox.util.db import drop_everything

        # Drop test DB
        drop_everything(self.engine, with_users=True)
