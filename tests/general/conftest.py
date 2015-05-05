""" Fixtures don't go here; see util/base.py and friends. """
from gevent import monkey
monkey.patch_all(aggressive=False)

# fixtures that are available by default
from tests.util.base import (config, db, log, absolute_path, default_namespace,
                             default_account, thread, folder, message, imapuid,
                             raw_message)


def pytest_generate_tests(metafunc):
    if 'db' in metafunc.fixturenames:
        dumpfile = absolute_path(config()['BASE_DUMP'])
        savedb = False

        metafunc.parametrize('db', [(dumpfile, savedb)], indirect=True)
