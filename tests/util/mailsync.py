from pytest import fixture

from tests.util.base import TestZeroRPC, db


@fixture(scope='session')
def sync_client(config, db):
    sync_service_loc = config.get('CRISPIN_SERVER_LOC')

    from inbox.server.mailsync.service import SyncService

    test = TestZeroRPC(config, db, SyncService, sync_service_loc)

    return test.client
