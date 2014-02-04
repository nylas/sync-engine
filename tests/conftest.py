""" Fixtures in this file are available to all files automatically, no
    importing required. Only put general purpose fixtures here!
"""
import pytest
import os

from shutil import rmtree

TEST_CONFIG = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'config.cfg')

@pytest.fixture(scope='session', autouse=True)
def config():
    from inbox.server.config import load_config, config
    load_config(filename=TEST_CONFIG)
    return config

# XXX is this the right scope for this? This will remove log/ at the end of
# the test session.
@pytest.fixture(scope='session')
def log(request, config):
    """ Returns root server logger. For others loggers, use this fixture
        for setup but then call inbox.server.log.get_logger().
    """
    from inbox.server.log import configure_general_logging
    def remove_logs():
        rmtree(config['LOGDIR'], ignore_errors=True)
    request.addfinalizer(remove_logs)
    return configure_general_logging()
