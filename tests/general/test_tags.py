"""Exercise the tags API."""
import json
import gevent
from tests.util.base import api_client


# Utility functions to simplify hitting the API.

def full_path(api_client, path):
    """For testing purposes, replace a path such as '/tags' by
    '/n/<ns_id>/tags', where <ns_id> is the id of the first result of a call to
    '/n/'."""
    namespace_id = json.loads(api_client.get('/n/').data)[0]['id']
    return '/n/{}'.format(namespace_id) + path


def get_data(client, short_path):
    path = full_path(client, short_path)
    return json.loads(client.get(path).data)


def post_data(client, short_path, data):
    path = full_path(client, short_path)
    return client.post(path, data=json.dumps(data))


def put_data(client, short_path, data):
    path = full_path(client, short_path)
    return client.put(path, data=json.dumps(data))


def get_tag_names(thread):
    return [tag['name'] for tag in thread['tags']]


def kill_greenlets():
    """Utility function to kill all running greenlets."""
    import gc
    for obj in gc.get_objects():
        if isinstance(obj, gevent.Greenlet):
            obj.kill()


def test_get_tags(api_client):
    from inbox.models.tables.base import Tag
    tags = get_data(api_client, '/tags')
    assert set(Tag.RESERVED_TAG_NAMES).issubset({tag['name'] for tag in tags})


def test_create_tag(api_client):
    post_data(api_client, '/tags', {'name': 'foo'})
    assert 'foo' in [tag['name'] for tag in get_data(api_client, '/tags')]


def test_cant_create_existing_tag(api_client):
    post_data(api_client, '/tags', {'name': 'foo'})
    r = post_data(api_client, '/tags', {'name': 'foo'})
    assert r.status_code == 409


def test_add_remove_tags(api_client):
    assert 'foo' not in [tag['name'] for tag in get_data(api_client, '/tags')]
    assert 'bar' not in [tag['name'] for tag in get_data(api_client, '/tags')]

    post_data(api_client, '/tags', {'name': 'foo'})
    post_data(api_client, '/tags', {'name': 'bar'})

    thread_id = get_data(api_client, '/threads')[0]['id']
    thread_path = '/threads/{}'.format(thread_id)
    put_data(api_client, thread_path, {'add_tags': ['foo']})
    put_data(api_client, thread_path, {'add_tags': ['bar']})

    tag_names = [tag['name'] for tag in
                 get_data(api_client, thread_path)['tags']]
    assert 'foo' in tag_names
    assert 'bar' in tag_names

    # Check that tag was only applied to this thread
    another_thread_id = get_data(api_client, '/threads')[1]['id']
    tag_names = get_tag_names(get_data(api_client, '/threads/{}'.
                                       format(another_thread_id)))
    assert 'foo' not in tag_names

    put_data(api_client, thread_path, {'remove_tags': ['foo']})
    put_data(api_client, thread_path, {'remove_tags': ['bar']})
    tag_names = get_tag_names(get_data(api_client, thread_path))
    assert 'foo' not in tag_names
    assert 'bar' not in tag_names


def test_tag_deletes_cascade_to_threads():
    # TODO(emfree)
    pass


class MockQueue(list):
    """Used to mock out the SyncbackService queue (with just a list)."""
    def __init__(self):
        list.__init__(self)

    def enqueue(self, *args):
        self.append(args)


def test_actions_syncback(api_client):
    """Add and remove tags that should trigger syncback actions, and check that
    the appropriate actions get put on the queue (doesn't test the
    implementation of the actual syncback methods in
    inbox/actions/base.py)."""
    from inbox.transactions.actions import SyncbackService
    from inbox.actions.base import (mark_read, mark_unread, archive,
                                           unarchive, star, unstar)
    from gevent import monkey
    # aggressive=False used to avoid AttributeError in other tests, see
    # https://groups.google.com/forum/#!topic/gevent/IzWhGQHq7n0
    # TODO(emfree): It's totally whack that monkey-patching here would affect
    # other tests. Can we make this not happen?
    monkey.patch_all(aggressive=False)
    s = SyncbackService(poll_interval=0)
    s.queue = MockQueue()
    s.start()
    gevent.sleep()
    assert len(s.queue) == 0

    thread_id = get_data(api_client, '/threads')[0]['id']
    thread_path = '/threads/{}'.format(thread_id)

    # Make sure tags are removed to start with
    put_data(api_client, thread_path, {'remove_tags': ['unread']})
    put_data(api_client, thread_path, {'remove_tags': ['archive']})
    put_data(api_client, thread_path, {'remove_tags': ['starred']})

    # Add and remove tags that should trigger actions

    put_data(api_client, thread_path, {'add_tags': ['unread']})
    put_data(api_client, thread_path, {'remove_tags': ['unread']})

    put_data(api_client, thread_path, {'add_tags': ['archive']})
    put_data(api_client, thread_path, {'remove_tags': ['archive']})

    put_data(api_client, thread_path, {'add_tags': ['starred']})
    put_data(api_client, thread_path, {'remove_tags': ['starred']})

    gevent.sleep()

    queued_actions = [item[0] for item in s.queue]
    for action in [mark_read, mark_unread, archive, unarchive, star, unstar]:
        assert action in queued_actions

    kill_greenlets()
