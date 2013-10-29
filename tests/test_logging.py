import os
from logging import getLogger

def test_root_filelogger(config, log):
    log.warning('TEST LOG STATEMENT')
    root_logger = getLogger()
    root_logger.warning('ROOT LOG STATEMENT')
    # NOTE: This slurps the whole logfile. Hope it's not big.
    log_contents = open(os.path.join(config['LOGDIR'], 'server.log'), 'r').read()
    assert 'TEST LOG STATEMENT' in log_contents
    assert 'ROOT LOG STATEMENT' not in log_contents

def test_sync_filelogger(config, log):
    pass
