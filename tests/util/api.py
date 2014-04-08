from pytest import fixture

from tests.util.base import TestZeroRPC, db


@fixture(scope='function')
def api_client(config, db):
    api_service_loc = config.get('API_SERVER_LOC')

    from inbox.server.api import API

    test = TestZeroRPC(config, db, API, api_service_loc)

    return test.client
