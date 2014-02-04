from pytest import fixture

from .base import TestZeroRPC, db

@fixture(scope='session')
def api_client(config, db):
    api_service_loc = config.get('API_SERVER_LOC')

    from inbox.server.api import API

    test = TestZeroRPC(config, db, API, api_service_loc)

    return test.client
