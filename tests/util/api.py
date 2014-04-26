from pytest import fixture

from tests.util.base import TestZeroRPC


@fixture(scope='session')
def api_client(config):
    api_service_loc = config.get('API_SERVER_LOC')

    from inbox.server.api import API

    test = TestZeroRPC(config, API, api_service_loc)

    return test.client
