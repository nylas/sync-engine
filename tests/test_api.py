import zerorpc, pytest
from base import Test

API_SERVER_LOC = 'tcp://0.0.0.0:9999'
ML_MID = 2

@pytest.fixture(scope='session', autouse=True)
def api_client(request):
    test = Test()
    test.client = zerorpc.Client(timeout=5)
    test.client.connect(API_SERVER_LOC)

    def fin():
    	test.destroy()
    	request.addfinalizer(fin)

    return test.client

def test_is_mailing_list_message(api_client):
     result = api_client.is_mailing_list_message(ML_MID)
     assert (result == True)

# def test_mailing_list_info_for_message(api_client):
#     result = api_client.mailing_list_info_for_message(ML_MID)
#     print result

# def test_headers_for_message(api_client):
#     result = api_client.headers_for_message()
#     print result