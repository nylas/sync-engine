import json
import time
from tests.util.base import add_fake_message
from tests.api.base import api_client

__all__ = ['api_client']


def get_cursor(api_client, timestamp):
    cursor_response = api_client.post_data('/delta/generate_cursor',
                                           {'start': timestamp})
    return json.loads(cursor_response.data)['cursor']


def test_latest_cursor(api_client):
    now = int(time.time())
    latest_cursor_resp = api_client.post_raw('/delta/latest_cursor', None)
    latest_cursor = json.loads(latest_cursor_resp.data)['cursor']
    now_cursor = get_cursor(api_client, now)
    assert latest_cursor == now_cursor


def test_invalid_input(api_client):
    cursor_response = api_client.post_data('/delta/generate_cursor',
                                           {'start': "I'm not a timestamp!"})
    assert cursor_response.status_code == 400

    sync_response = api_client.client.get(
        '/delta?cursor={}'.format('fake cursor'),
        headers=api_client.auth_header)
    assert sync_response.status_code == 400


def test_events_are_condensed(api_client, message):
    """
    Test that multiple revisions of the same object are rolled up in the
    delta response.

    """
    ts = int(time.time() + 22)
    cursor = get_cursor(api_client, ts)

    # Modify a message, then modify it again
    message_id = api_client.get_data('/messages/')[0]['id']
    message_path = '/messages/{}'.format(message_id)
    api_client.put_data(message_path, {'unread': True})
    api_client.put_data(message_path, {'unread': False})
    api_client.put_data(message_path, {'unread': True})

    # Check that successive modifies are condensed.
    sync_data = api_client.get_data('/delta?cursor={}'.format(cursor))
    deltas = sync_data['deltas']
    # A message modify propagates to its thread
    message_deltas = [d for d in deltas if d['object'] == 'message']
    assert len(message_deltas) == 1

    delta = message_deltas[0]
    assert delta['object'] == 'message' and delta['event'] == 'modify'
    assert delta['attributes']['unread'] is True


def test_message_events_are_propagated_to_thread(api_client, message):
    """
    Test that a revision to a message's `propagated_attributes` returns a delta
    for the message and for its thread.

    """
    ts = int(time.time() + 22)
    cursor = get_cursor(api_client, ts)

    message = api_client.get_data('/messages/')[0]
    message_id = message['id']
    assert message['unread'] is True

    thread = api_client.get_data('/threads/{}'.format(message['thread_id']))
    assert thread['unread'] is True

    # Modify a `propagated_attribute` of the message
    message_path = '/messages/{}'.format(message_id)
    api_client.put_data(message_path, {'unread': False})

    # Verify that a `message` and a `thread` modify delta is returned
    sync_data = api_client.get_data('/delta?cursor={}'.format(cursor))
    deltas = sync_data['deltas']
    assert len(deltas) == 2

    message_deltas = [d for d in deltas if d['object'] == 'message']
    assert len(message_deltas) == 1
    delta = message_deltas[0]
    assert delta['object'] == 'message' and delta['event'] == 'modify'
    assert delta['attributes']['unread'] is False

    thread_deltas = [d for d in deltas if d['object'] == 'thread']
    assert len(thread_deltas) == 1
    delta = thread_deltas[0]
    assert delta['object'] == 'thread' and delta['event'] == 'modify'
    assert delta['attributes']['unread'] is False
    assert delta['attributes']['version'] == thread['version'] + 1


def test_handle_missing_objects(api_client, db, thread, default_namespace):
    ts = int(time.time() + 22)
    cursor = get_cursor(api_client, ts)

    messages = []
    for _ in range(100):
        messages.append(add_fake_message(db.session, default_namespace.id,
                                         thread))
    for message in messages:
        db.session.delete(message)
    db.session.commit()
    sync_data = api_client.get_data('/delta?cursor={}&exclude_types=thread'.
                                    format(cursor))
    assert len(sync_data['deltas']) == 100
    assert all(delta['event'] == 'delete' for delta in sync_data['deltas'])
