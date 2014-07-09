"""Exercise the tags API."""
import gevent
import pytest
from tests.util.base import api_client, mock_syncback_service


# Utility functions to simplify hitting the API.

def get_tag_names(thread):
    return [tag['name'] for tag in thread['tags']]

@pytest.fixture(autouse=True)
def create_canonical_tags(db):
    """Ensure that all canonical tags exist for the namespace we're testing
    against. This is normally done when an account sync starts."""
    from inbox.models import Namespace, Tag
    namespace = db.session.query(Namespace).first()
    Tag.create_canonical_tags(namespace, db.session)
    db.session.commit()


def test_get_tags(api_client):
    from inbox.models import Tag
    tags = api_client.get_data('/tags/')
    assert set(Tag.RESERVED_TAG_NAMES).issubset({tag['name'] for tag in tags})


def test_create_tag(api_client):
    api_client.post_data('/tags/', {'name': 'foo'})
    assert 'foo' in [tag['name'] for tag in api_client.get_data('/tags/')]


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


def test_actions_syncback(api_client, mock_syncback_service):
    """Adds and removes tags that should trigger syncback actions, and check
    that the appropriate actions get spawned (but doesn't test the
    implementation of the actual syncback methods in inbox.actions).
    """
    from inbox.actions import (mark_read, mark_unread, archive, unarchive,
                               star, unstar)

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

    gevent.sleep()

    for action in [mark_read, mark_unread, archive, unarchive, star, unstar]:
        assert action in mock_syncback_service.scheduled_actions
