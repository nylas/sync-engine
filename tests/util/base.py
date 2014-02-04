import os, subprocess

from inbox.util.db import drop_everything

TEST_DATA = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), '..',
    'data', 'base_dump.sql')

class TestDB(object):
    def __init__(self, config):
        from inbox.server.models import new_db_session, init_db, engine
        # Set up test database
        init_db()
        self.db_session = new_db_session()
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
        drop_everything(self.engine, with_users=True)
