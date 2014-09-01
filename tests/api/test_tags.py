"""Exercise the tags API."""
import json
import gevent
import pytest
from inbox.models import Tag

from tests.util.base import (patch_network_functions, api_client,
                             syncback_service, default_namespace)

__all__ = ['patch_network_functions', 'api_client', 'syncback_service',
           'default_namespace']


# Utility functions to simplify hitting the API.

def get_tag_names(thread):
    return [tag['name'] for tag in thread['tags']]


@pytest.fixture(autouse=True)
def create_canonical_tags(db, default_namespace):
    """Ensure that all canonical tags exist for the namespace we're testing
    against. This is normally done when an account sync starts."""
    Tag.create_canonical_tags(default_namespace, db.session)
    db.session.commit()


def test_get_tags(api_client):
    tags = api_client.get_data('/tags/')
    assert set(Tag.RESERVED_TAG_NAMES).issubset({tag['name'] for tag in tags})


def test_get_invalid(api_client):
    bad_tag_id = '0000000000000000000000000'
    tag_data = api_client.get_data('/tags/{}'.format(bad_tag_id))
    assert tag_data['message'] == 'No tag found'

    bad_tag_id = 'asdf!'
    tag_data = api_client.get_data('/tags/{}'.format(bad_tag_id))
    assert 'is not a valid id' in tag_data['message']


def test_create_tag(api_client, default_namespace):
    ns_id = default_namespace.public_id

    post_resp = api_client.post_data('/tags/', {'name': 'foo'})
    assert post_resp.status_code == 200
    tag_resp = json.loads(post_resp.data)
    assert tag_resp['name'] == 'foo'
    assert tag_resp['namespace_id'] == ns_id
    tag_id = tag_resp['id']

    # Check getting the tag
    tag_data = api_client.get_data('/tags/{}'.format(tag_id))
    assert tag_data['name'] == 'foo'
    assert tag_data['namespace_id'] == ns_id
    assert tag_data['id'] == tag_id

    # Check listing the tag
    assert 'foo' in [tag['name'] for tag in api_client.get_data('/tags/')]

    # Make sure we can specify the namespace that we are creating the tag in
    bad_ns_id = 0000000000000000000000000
    tag_data = {'name': 'foo3', 'namespace_id': bad_ns_id}
    put_resp = api_client.post_data('/tags/', tag_data)
    assert put_resp.status_code == 400
    assert 'foo3' not in [tag['name'] for tag in api_client.get_data('/tags/')]

    # Make sure that we can only update to the existing namespace


def test_create_invalid(api_client, default_namespace):
    from inbox.models.constants import MAX_INDEXABLE_LENGTH
    bad_ns_id = '0000000000000000000000000'

    post_resp = api_client.post_data('/tags/', {'invalid': 'foo'})
    assert post_resp.status_code == 400

    new_tag_data = {'name': 'foo', 'namespace_id': bad_ns_id}
    post_resp = api_client.post_data('/tags/', new_tag_data)
    assert post_resp.status_code == 400

    too_long = 'x' * (MAX_INDEXABLE_LENGTH + 1)
    post_resp = api_client.post_data('/tags/', {'name': too_long})
    assert post_resp.status_code == 400
    assert 'too long' in json.loads(post_resp.data)['message']


def test_read_update_tags(api_client):
    r = api_client.post_data('/tags/', {'name': 'foo'})
    public_id = json.loads(r.data)['id']

    tag_data = api_client.get_data('/tags/{}'.format(public_id))
    assert tag_data['name'] == 'foo'
    assert tag_data['id'] == public_id
    tag_ns_id = tag_data['namespace_id']

    r = api_client.put_data('/tags/{}'.format(public_id), {'name': 'bar'})
    assert json.loads(r.data)['name'] == 'bar'

    # include namespace
    r = api_client.put_data('/tags/{}'.format(public_id),
                            {'name': 'bar', 'namepace_id': tag_ns_id})
    assert json.loads(r.data)['name'] == 'bar'

    updated_tag_data = api_client.get_data('/tags/{}'.format(public_id))
    assert updated_tag_data['name'] == 'bar'
    assert updated_tag_data['id'] == public_id


def test_update_invalid(api_client):
    not_found_id = '0000000000000000000000000'
    r = api_client.put_data('/tags/{}'.format(not_found_id), {'name': 'bar'})
    assert r.status_code == 404

    bad_id = '!'
    r = api_client.put_data('/tags/{}'.format(bad_id), {'name': 'bar'})
    assert r.status_code == 400

    post_resp = api_client.post_data('/tags/', {'name': 'foo'})
    tag_id = json.loads(post_resp.data)['id']
    r = api_client.put_data('/tags/{}'.format(tag_id), {'invalid': 'bar'})
    assert r.status_code == 400

    # create a conflict
    post_resp = api_client.post_data('/tags/', {'name': 'foo_conflict'})
    r = api_client.put_data('/tags/{}'.format(tag_id),
                            {'name': 'foo_conflict'})
    assert r.status_code == 409

    # try to move namespaces
    tag_update = {'name': 'foo3', 'namespace_id': not_found_id}
    r = api_client.put_data('/tags/{}'.format(tag_id), tag_update)
    assert r.status_code == 400


def test_can_only_update_user_tags(api_client):
    r = api_client.get_data('/tags/unread')
    assert r['name'] == 'unread'
    assert r['id'] == 'unread'

    r = api_client.put_data('/tags/unread', {'name': 'new name'})
    assert r.status_code == 403


def test_cant_create_existing_tag(api_client):
    api_client.post_data('/tags/', {'name': 'foo'})
    r = api_client.post_data('/tags/', {'name': 'foo'})
    assert r.status_code == 409


def test_add_remove_tags(api_client):
    assert 'foo' not in [tag['name'] for tag in api_client.get_data('/tags/')]
    assert 'bar' not in [tag['name'] for tag in api_client.get_data('/tags/')]

    api_client.post_data('/tags/', {'name': 'foo'})
    api_client.post_data('/tags/', {'name': 'bar'})

    thread_id = api_client.get_data('/threads/')[0]['id']
    thread_path = '/threads/{}'.format(thread_id)
    api_client.put_data(thread_path, {'add_tags': ['foo']})
    api_client.put_data(thread_path, {'add_tags': ['bar']})

    tag_names = [tag['name'] for tag in
                 api_client.get_data(thread_path)['tags']]
    assert 'foo' in tag_names
    assert 'bar' in tag_names

    # Check that tag was only applied to this thread
    another_thread_id = api_client.get_data('/threads/')[1]['id']
    tag_names = get_tag_names(
        api_client.get_data('/threads/{}'.format(another_thread_id)))
    assert 'foo' not in tag_names

    api_client.put_data(thread_path, {'remove_tags': ['foo']})
    api_client.put_data(thread_path, {'remove_tags': ['bar']})
    tag_names = get_tag_names(api_client.get_data(thread_path))
    assert 'foo' not in tag_names
    assert 'bar' not in tag_names


def test_tag_permissions(api_client, db):
    from inbox.models import Tag
    thread_id = api_client.get_data('/threads/')[0]['id']
    thread_path = '/threads/{}'.format(thread_id)
    for canonical_name in Tag.RESERVED_TAG_NAMES:
        r = api_client.put_data(thread_path, {'add_tags': [canonical_name]})
        if canonical_name in Tag.USER_MUTABLE_TAGS:
            assert r.status_code == 200
        else:
            assert r.status_code == 400

    # Test special permissions of the 'unseen' tag
    r = api_client.put_data(thread_path, {'add_tags': ['unseen']})
    assert r.status_code == 400

    r = api_client.put_data(thread_path, {'remove_tags': ['unseen']})
    assert r.status_code == 200


def test_read_implies_seen(api_client, db):
    thread_id = api_client.get_data('/threads/')[0]['id']
    thread_path = '/threads/{}'.format(thread_id)
    # Do some setup: cheat by making sure the unseen and unread tags are
    # already on the thread.
    from inbox.models import Namespace, Thread
    namespace = db.session.query(Namespace).first()
    unseen_tag = namespace.tags['unseen']
    unread_tag = namespace.tags['unread']
    thread = db.session.query(Thread).filter_by(public_id=thread_id).one()
    thread.tags.add(unseen_tag)
    thread.tags.add(unread_tag)
    db.session.commit()

    r = api_client.get_data(thread_path)
    assert {'unread', 'unseen'}.issubset({tag['id'] for tag in r['tags']})

    r = api_client.put_data(thread_path, {'remove_tags': ['unread']})
    r = api_client.get_data(thread_path)
    assert not any(tag['id'] in ['unread', 'unseen'] for tag in r['tags'])


def test_tag_deletes_cascade_to_threads():
    # TODO(emfree)
    pass


def test_actions_syncback(patch_network_functions, api_client, db,
                          syncback_service):
    """Adds and removes tags that should trigger syncback actions, and check
    that the appropriate actions get spawned (but doesn't test the
    implementation of the actual syncback methods in inbox.actions).
    """
    from inbox.models import ActionLog

    thread_id = api_client.get_data('/threads/')[0]['id']
    thread_path = '/threads/{}'.format(thread_id)

    # Make sure tags are removed to start with
    api_client.put_data(thread_path, {'remove_tags': ['unread']})
    api_client.put_data(thread_path, {'remove_tags': ['archive']})
    api_client.put_data(thread_path, {'remove_tags': ['starred']})

    # Add and remove tags that should trigger actions

    api_client.put_data(thread_path, {'add_tags': ['unread']})
    api_client.put_data(thread_path, {'remove_tags': ['unread']})

    api_client.put_data(thread_path, {'add_tags': ['archive']})
    api_client.put_data(thread_path, {'remove_tags': ['archive']})

    api_client.put_data(thread_path, {'add_tags': ['starred']})
    api_client.put_data(thread_path, {'remove_tags': ['starred']})

    gevent.sleep(2)

    action_log_entries = db.session.query(ActionLog)
    assert ({log_entry.action for log_entry in action_log_entries} ==
            {'mark_read', 'mark_unread', 'archive', 'unarchive', 'star',
             'unstar'})
    assert all(log_entry.executed for log_entry in action_log_entries)
