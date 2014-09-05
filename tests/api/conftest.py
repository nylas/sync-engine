""" Fixtures don't go here; see util/base.py and friends. """
# Load test config before inbox.* imports +
# fixtures that are available by default
from tests.util.base import config, db, log, absolute_path
config()


def pytest_generate_tests(metafunc):
    if 'db' in metafunc.fixturenames:
        dumpfile = absolute_path(config()['BASE_DUMP'])
        savedb = False

        metafunc.parametrize('db', [(dumpfile, savedb)], indirect=True)
