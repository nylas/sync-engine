import zerorpc, pytest
from . import test_base

API_SERVER_LOC = 'tcp://0.0.0.0:9999'
ML_MID = 2

@pytest.fixture(scope='session', autouse=True)
def test_client():
    test = test_base.Test()
    test.client = zerorpc.Client(timeout=5)
    test.client.connect(API_SERVER_LOC)

    return test.client

def test_is_mailing_list_message(test_client):
    result = test_client.is_mailing_list_message(ML_MID)
    assert (result == True)

def test_mailing_list_info_for_message(test_client):
    result = test_client.mailing_list_info_for_message(ML_MID)
    print result

def test_headers_for_message(test_client):
    result = test_client.headers_for_message()