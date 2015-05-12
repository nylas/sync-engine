import json
import time
import pytest
from tests.util.base import default_namespace
from inbox.models import Namespace
from inbox.util.url import url_concat


@pytest.yield_fixture
def streaming_test_client(db):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def api_prefix(default_namespace):
    return '/n/{}/delta/streaming'.format(default_namespace.public_id)


def get_cursor(api_client, timestamp, namespace):
    cursor_response = api_client.post(
        '/n/{}/delta/generate_cursor'.format(namespace.public_id),
        data=json.dumps({'start': timestamp}))
    return json.loads(cursor_response.data)['cursor']


def validate_response_format(response_string):
    response = json.loads(response_string)
    assert 'cursor' in response
    assert 'attributes' in response
    assert 'object' in response
    assert 'id' in response
    assert 'event' in response


def test_response_when_old_cursor_given(db, api_prefix, streaming_test_client,
                                        default_namespace):
    url = url_concat(api_prefix, {'timeout': .1,
                                  'cursor': '0'})
    r = streaming_test_client.get(url)
    assert r.status_code == 200
    responses = r.data.split('\n')
    for response_string in responses:
        if response_string:
            validate_response_format(response_string)


def test_empty_response_when_latest_cursor_given(db, api_prefix,
                                                 streaming_test_client,
                                                 default_namespace):
    cursor = get_cursor(streaming_test_client, int(time.time()),
                        default_namespace)
    url = url_concat(api_prefix, {'timeout': .1,
                                  'cursor': cursor})
    r = streaming_test_client.get(url)
    assert r.status_code == 200
    assert r.data.strip() == ''


def test_gracefully_handle_new_namespace(db, streaming_test_client):
    new_namespace = Namespace()
    db.session.add(new_namespace)
    db.session.commit()
    cursor = get_cursor(streaming_test_client, int(time.time()),
                        new_namespace)
    url = url_concat('/n/{}/delta/streaming'.format(new_namespace.public_id),
                     {'timeout': .1, 'cursor': cursor})
    r = streaming_test_client.get(url)
    assert r.status_code == 200


def test_exclude_object_types(db, api_prefix, streaming_test_client):
    # Check that we do get message and contact changes by default.
    url = url_concat(api_prefix, {'timeout': .1,
                                  'cursor': '0'})
    r = streaming_test_client.get(url)
    assert r.status_code == 200
    responses = r.data.split('\n')
    parsed_responses = [json.loads(resp) for resp in responses if resp != '']
    assert any(resp['object'] == 'message' for resp in parsed_responses)
    assert any(resp['object'] == 'contact' for resp in parsed_responses)

    # And check that we don't get message/contact changes if we exclude them.
    url = url_concat(api_prefix, {'timeout': .1,
                                  'cursor': '0',
                                  'exclude_types': 'message,contact'})
    r = streaming_test_client.get(url)
    assert r.status_code == 200
    responses = r.data.split('\n')
    parsed_responses = [json.loads(resp) for resp in responses if resp != '']
    assert not any(resp['object'] == 'message' for resp in parsed_responses)
    assert not any(resp['object'] == 'contact' for resp in parsed_responses)
