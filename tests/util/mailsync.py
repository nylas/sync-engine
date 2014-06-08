from pytest import fixture

from tests.util.base import TestZeroRPC


@fixture(scope='session')
def sync_client(config):
    sync_service_loc = config.get('CRISPIN_SERVER_LOC')

    from inbox.mailsync.service import SyncService

    test = TestZeroRPC(config, SyncService, sync_service_loc)

    return test.client
