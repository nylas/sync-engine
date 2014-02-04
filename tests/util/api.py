import pytest, zerorpc

from .base import TestDB

@pytest.fixture(scope='session')
def api_client(config, request):
    test = TestDB()

    api_server_loc = config.get('API_SERVER_LOC')

    from inbox.server.api import API
    from inbox.server.util.concurrency import make_zerorpc

    test.server = make_zerorpc(API, api_server_loc)

    test.client = zerorpc.Client(timeout=5)
    test.client.connect(api_server_loc)

    request.addfinalizer(test.destroy)

    return test.client
