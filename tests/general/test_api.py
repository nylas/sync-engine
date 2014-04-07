import json
from bson import json_util

# pytest fixtures outside of conftest.py must be imported for discovery
from tests.util.api import api_client
from tests.util.mailsync import sync_client
from tests.data.messages.message import TEST_MSG

USER_ID = 1
NAMESPACE_ID = 1


def test_sync_status(api_client, sync_client):
    result = api_client.sync_status()
    # TODO(emfree): actually run a sync and test the result
    expected = '{}'
    assert (result == expected)


def test_is_mailing_list_thread(api_client):
    result = api_client.is_mailing_list_thread(USER_ID, NAMESPACE_ID,
                                               TEST_MSG['thread_id'])
    expected = True

    assert (result == expected)


def test_mailing_list_info_for_thread(api_client):
    result = api_client.mailing_list_info_for_thread(USER_ID, NAMESPACE_ID,
                                                     TEST_MSG['thread_id'])
    expected = json.dumps(TEST_MSG['mailing_list_headers'],
                          default=json_util.default)

    assert (result == expected)


def test_headers_for_message(api_client):
    result = api_client.headers_for_message(USER_ID, NAMESPACE_ID,
                                            TEST_MSG['msg_id'])
    expected = TEST_MSG['all_headers']

    assert (result == expected)
