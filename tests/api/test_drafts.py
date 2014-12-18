"""Test local behavior for the drafts API. Doesn't test syncback or actual
sending."""
import json
import os
import time
from datetime import datetime

import gevent
import pytest

from tests.util.base import (patch_network_functions, api_client,
                             syncback_service, default_account)

__all__ = ['patch_network_functions', 'api_client', 'syncback_service']

NAMESPACE_ID = 1


@pytest.fixture
def example_draft(db):
    from inbox.models import Account
    account = db.session.query(Account).get(1)
    return {
        'subject': 'Draft test at {}'.format(datetime.utcnow()),
        'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>',
        'to': [{'name': 'The red-haired mermaid',
                'email': account.email_address}]
    }


@pytest.fixture(scope='function')
def attachments(db):
    filenames = ['muir.jpg', 'LetMeSendYouEmail.wav', 'first-attachment.jpg']
    data = []
    for filename in filenames:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                            'data', filename)
        data.append((filename, path))
    return data


def test_create_and_get_draft(api_client, example_draft):
    r = api_client.post_data('/drafts', example_draft)
    assert r.status_code == 200

    public_id = json.loads(r.data)['id']
    version = json.loads(r.data)['version']
    assert public_id != version

    r = api_client.get_data('/drafts')
    matching_saved_drafts = [draft for draft in r if draft['id'] == public_id]
    assert len(matching_saved_drafts) == 1
    saved_draft = matching_saved_drafts[0]

    assert saved_draft['state'] == 'draft'
    assert all(saved_draft[k] == v for k, v in example_draft.iteritems())

    # Check that thread gets the draft tag
    threads_with_drafts = api_client.get_data('/threads?tag=drafts')
    assert len(threads_with_drafts) == 1

    # Check that thread doesn't get the attachment tag, in this case
    thread_tags = threads_with_drafts[0]['tags']
    assert not any('attachment' == tag['name'] for tag in thread_tags)


def test_create_reply_draft(api_client):
    thread_public_id = api_client.get_data('/threads')[0]['id']

    reply_draft = {
        'subject': 'test reply',
        'body': 'test reply',
        'thread_id': thread_public_id
    }
    r = api_client.post_data('/drafts', reply_draft)
    draft_public_id = json.loads(r.data)['id']

    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 1
    assert drafts[0]['state'] == 'draft'

    assert thread_public_id == drafts[0]['thread_id']

    thread_data = api_client.get_data('/threads/{}'.format(thread_public_id))
    assert draft_public_id in thread_data['draft_ids']


def test_drafts_filter(api_client, example_draft):
    r = api_client.post_data('/drafts', example_draft)
    public_id = json.loads(r.data)['id']

    r = api_client.get_data('/drafts')
    matching_saved_drafts = [draft for draft in r if draft['id'] == public_id]
    thread_public_id = matching_saved_drafts[0]['thread_id']

    reply_draft = {
        'subject': 'test reply',
        'body': 'test reply',
        'thread_id': thread_public_id
    }
    r = api_client.post_data('/drafts', reply_draft)

    _filter = '?thread_id=0000000000000000000000000'
    results = api_client.get_data('/drafts' + _filter)
    assert len(results) == 0

    results = api_client.get_data('/drafts?thread_id={}'
                                  .format(thread_public_id))
    assert len(results) == 2

    results = api_client.get_data('/drafts?offset={}&thread_id={}'
                                  .format(1, thread_public_id))
    assert len(results) == 1


def test_create_draft_with_attachments(api_client, attachments, example_draft):
    attachment_ids = []
    upload_path = api_client.full_path('/files')
    for filename, path in attachments:
        data = {'file': (open(path, 'rb'), filename)}
        r = api_client.client.post(upload_path, data=data)
        assert r.status_code == 200
        attachment_id = json.loads(r.data)[0]['id']
        attachment_ids.append(attachment_id)

    first_attachment = attachment_ids.pop()

    example_draft['file_ids'] = [first_attachment]
    r = api_client.post_data('/drafts', example_draft)
    assert r.status_code == 200
    returned_draft = json.loads(r.data)
    draft_public_id = returned_draft['id']
    example_draft['version'] = returned_draft['version']
    assert len(returned_draft['files']) == 1

    attachment_ids.append(first_attachment)
    example_draft['file_ids'] = attachment_ids
    r = api_client.put_data('/drafts/{}'.format(draft_public_id),
                            example_draft)
    assert r.status_code == 200
    returned_draft = json.loads(r.data)
    assert len(returned_draft['files']) == 3
    example_draft['version'] = returned_draft['version']

    # Make sure we can't delete the files now
    for file_id in attachment_ids:
        r = api_client.delete('/files/{}'.format(file_id))
        assert r.status_code == 400

    threads_with_drafts = api_client.get_data('/threads?tag=drafts')
    assert len(threads_with_drafts) == 1

    # Check that thread also gets the attachment tag
    thread_tags = threads_with_drafts[0]['tags']
    assert any('attachment' == tag['name'] for tag in thread_tags)

    # Now remove the attachment
    example_draft['file_ids'] = [first_attachment]
    r = api_client.put_data('/drafts/{}'.format(draft_public_id),
                            example_draft)

    draft_data = api_client.get_data('/drafts/{}'.format(draft_public_id))
    assert len(draft_data['files']) == 1
    example_draft['version'] = draft_data['version']

    example_draft['file_ids'] = []
    r = api_client.put_data('/drafts/{}'.format(draft_public_id),
                            example_draft)
    draft_data = api_client.get_data('/drafts/{}'.format(draft_public_id))
    assert r.status_code == 200
    assert len(draft_data['files']) == 0
    returned_draft = json.loads(r.data)

    # now that they're not attached, we should be able to delete them
    for file_id in attachment_ids:
        r = api_client.delete('/files/{}'.format(file_id))
        assert r.status_code == 200


def test_get_all_drafts(api_client, example_draft):
    r = api_client.post_data('/drafts', example_draft)
    first_public_id = json.loads(r.data)['id']

    r = api_client.post_data('/drafts', example_draft)
    second_public_id = json.loads(r.data)['id']

    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 2
    assert first_public_id != second_public_id
    assert {first_public_id, second_public_id} == {draft['id'] for draft in
                                                   drafts}
    assert all(item['state'] == 'draft' and item['object'] == 'draft' for item
               in drafts)


def test_update_draft(api_client):
    original_draft = {
        'subject': 'parent draft',
        'body': 'parent draft'
    }
    r = api_client.post_data('/drafts', original_draft)
    draft_public_id = json.loads(r.data)['id']
    version = json.loads(r.data)['version']

    updated_draft = {
        'subject': 'updated draft',
        'body': 'updated draft',
        'version': version
    }

    r = api_client.put_data('/drafts/{}'.format(draft_public_id),
                            updated_draft)
    updated_public_id = json.loads(r.data)['id']
    updated_version = json.loads(r.data)['version']

    assert updated_public_id == draft_public_id and \
        updated_version != version

    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 1
    assert drafts[0]['id'] == updated_public_id


def test_delete_draft(api_client):
    original_draft = {
        'subject': 'parent draft',
        'body': 'parent draft'
    }
    r = api_client.post_data('/drafts', original_draft)
    draft_public_id = json.loads(r.data)['id']
    version = json.loads(r.data)['version']

    updated_draft = {
        'subject': 'updated draft',
        'body': 'updated draft',
        'version': version
    }
    r = api_client.put_data('/drafts/{}'.format(draft_public_id),
                            updated_draft)
    updated_public_id = json.loads(r.data)['id']
    updated_version = json.loads(r.data)['version']

    r = api_client.delete('/drafts/{}'.format(updated_public_id),
                          {'version': updated_version})

    # Check that drafts were deleted
    drafts = api_client.get_data('/drafts')
    assert not drafts

    # Check that no orphaned threads are around
    threads = api_client.get_data('/threads?subject=parent%20draft')
    assert not threads
    threads = api_client.get_data('/threads?subject=updated%20draft')
    assert not threads

    # And check that threads aren't deleted if they still have messages.
    thread_public_id = api_client.get_data('/threads')[0]['id']
    reply_draft = {
        'subject': 'test reply',
        'body': 'test reply',
        'thread_id': thread_public_id
    }
    r = api_client.post_data('/drafts', reply_draft)
    public_id = json.loads(r.data)['id']
    version = json.loads(r.data)['version']
    thread = api_client.get_data('/threads/{}'.format(thread_public_id))
    assert 'drafts' in [t['name'] for t in thread['tags']]
    api_client.delete('/drafts/{}'.format(public_id),
                      {'version': version})
    thread = api_client.get_data('/threads/{}'.format(thread_public_id))
    assert thread
    assert 'drafts' not in [t['name'] for t in thread['tags']]


def test_delete_remote_draft(db, api_client):
    from inbox.models.message import Message

    # Non-Inbox created draft, therefore don't set inbox_uid
    message = Message()
    message.namespace_id = NAMESPACE_ID
    message.thread_id = 1
    message.received_date = datetime.utcnow()
    message.size = len('')
    message.is_draft = True
    message.is_read = True
    message.sanitized_body = ''
    message.snippet = ''

    db.session.add(message)
    db.session.commit()

    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 1

    public_id = drafts[0]['id']
    version = drafts[0]['version']

    assert public_id == message.public_id and version == message.version

    api_client.delete('/drafts/{}'.format(public_id),
                      {'version': version})

    # Check that drafts were deleted
    drafts = api_client.get_data('/drafts')
    assert not drafts


def test_send(patch_network_functions, api_client, example_draft,
              syncback_service, default_account):
    r = api_client.post_data('/drafts', example_draft)
    draft_public_id = json.loads(r.data)['id']
    version = json.loads(r.data)['version']

    r = api_client.post_data('/send',
                             {'draft_id': draft_public_id,
                              'version': version})

    # TODO(emfree) do this more rigorously
    gevent.sleep(0.5)

    drafts = api_client.get_data('/drafts')
    threads_with_drafts = api_client.get_data('/threads?tag=drafts')
    assert not drafts
    assert not threads_with_drafts

    sent_threads = api_client.get_data('/threads?tag=sent')
    assert len(sent_threads) == 1

    message = api_client.get_data('/messages/{}'.format(draft_public_id))
    assert message['state'] == 'sent'
    assert message['object'] == 'message'


def test_handle_sending_failures(patch_network_functions, api_client,
                                 syncback_service):
    r = api_client.post_data('/send', {'to': [{'email': 'fail@example.com'}]})
    draft_public_id = json.loads(r.data)['id']
    start = time.time()
    while time.time() - start < 10:
        r = api_client.get_data('/drafts/{}'.format(draft_public_id))
        if r['state'] == 'sending failed':
            return
        gevent.sleep()
    assert False, 'sending not marked as failed before timeout'


def test_conflicting_updates(api_client):
    original_draft = {
        'subject': 'parent draft',
        'body': 'parent draft'
    }
    r = api_client.post_data('/drafts', original_draft)
    original_public_id = json.loads(r.data)['id']
    version = json.loads(r.data)['version']

    updated_draft = {
        'subject': 'updated draft',
        'body': 'updated draft',
        'version': version
    }
    r = api_client.put_data('/drafts/{}'.format(original_public_id),
                            updated_draft)
    assert r.status_code == 200
    updated_public_id = json.loads(r.data)['id']
    updated_version = json.loads(r.data)['version']
    assert updated_version != version

    conflicting_draft = {
        'subject': 'conflicting draft',
        'body': 'conflicting draft',
        'version': version
    }
    r = api_client.put_data('/drafts/{}'.format(original_public_id),
                            conflicting_draft)
    assert r.status_code == 409

    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 1
    assert drafts[0]['id'] == updated_public_id


def test_update_to_nonexistent_draft(api_client):
    updated_draft = {
        'subject': 'updated draft',
        'body': 'updated draft',
        'version': 'notarealversion'
    }

    r = api_client.put_data('/drafts/{}'.format('notarealid'), updated_draft)
    assert r.status_code == 404
    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 0


def test_contacts_updated(api_client):
    """Tests that draft-contact associations are properly created and
    updated."""
    draft = {
        'to': [{'email': 'alice@example.com'}, {'email': 'bob@example.com'}]
    }

    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 200
    draft_id = json.loads(r.data)['id']
    draft_version = json.loads(r.data)['version']

    r = api_client.get_data('/threads?to=alice@example.com')
    assert len(r) == 1

    updated_draft = {
        'to': [{'email': 'alice@example.com'}, {'email': 'joe@example.com'}],
        'version': draft_version
    }

    r = api_client.put_data('/drafts/{}'.format(draft_id), updated_draft)
    assert r.status_code == 200

    r = api_client.get_data('/threads?to=alice@example.com')
    assert len(r) == 1

    r = api_client.get_data('/threads?to=bob@example.com')
    assert len(r) == 0

    r = api_client.get_data('/threads?to=joe@example.com')
    assert len(r) == 1


def test_rate_limiting(patch_network_functions, api_client):
    """Test that sending is rate-limited appropriately.
    (Relies on a low value for DAILY_SENDING_LIMIT being set in the test
    config, for performance.)"""
    for _ in range(7):
        r = api_client.post_data('/send', {'to': [{'email':
                                                   'kermit@example.com'}]})
        assert r.status_code == 200
    r = api_client.post_data('/send', {'to': [{'email':
                                               'kermit@example.com'}]})
    assert r.status_code == 429
