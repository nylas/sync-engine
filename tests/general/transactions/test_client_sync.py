import json
import time
from tests.util.base import api_client


def test_invalid_input(api_client):
    stamp_response = api_client.post_data('/sync/generate_stamp',
                                          {'before': "I'm not a timestamp!"})
    assert stamp_response.status_code == 400

    sync_response = api_client.client.get(api_client.full_path(
        '/sync/events?stamp={}'.format('fake stamp'), 1))
    assert sync_response.status_code == 404


def test_event_generation(api_client):
    """Tests that events are returned in response to client sync API calls.
    Doesn't test formatting of individual events in the response."""
    ts = int(time.time())
    api_client.post_data('/tags', {'name': 'foo'})

    stamp_response = api_client.post_data('/sync/generate_stamp',
                                          {'before': ts})
    stamp = json.loads(stamp_response.data)['stamp']

    sync_data = api_client.get_data('/sync/events?stamp={}'.format(stamp))
    assert len(sync_data['events']) == 1
    api_client.post_data('/contacts', {'name': 'test',
                                       'email': 'test@example.com'})

    sync_data = api_client.get_data('/sync/events?stamp={}'.format(stamp))
    assert len(sync_data['events']) == 2

    thread_id = api_client.get_data('/threads')[0]['id']
    thread_path = '/threads/{}'.format(thread_id)
    api_client.put_data(thread_path, {'add_tags': ['foo']})

    sync_data = api_client.get_data('/sync/events?stamp={}'.format(stamp))
    assert len(sync_data['events']) == 3

    time.sleep(1)

    ts = int(time.time())

    # Test result limiting
    for _ in range(5):
        api_client.put_data(thread_path, {'remove_tags': ['foo']})
        api_client.put_data(thread_path, {'add_tags': ['foo']})

    stamp_response = api_client.post_data('/sync/generate_stamp',
                                          {'before': ts})
    stamp = json.loads(stamp_response.data)['stamp']

    sync_data = api_client.get_data('/sync/events?stamp={0}&limit={1}'.
                                    format(stamp, 8))
    assert len(sync_data['events']) == 8

    stamp = sync_data['next_event']
    sync_data = api_client.get_data('/sync/events?stamp={0}'.format(stamp))
    assert len(sync_data['events']) == 2
