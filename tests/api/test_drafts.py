"""Test local behavior for the drafts API. Doesn't test syncback or actual
sending."""
import json
import os
from datetime import datetime

import gevent
import pytest

from tests.util.base import (patch_network_functions, api_client,
                             syncback_service)

NAMESPACE_ID = 1


@pytest.fixture
def example_draft(db):
    from inbox.models import Account
    account = db.session.query(Account).get(1)
    return {
        'subject': 'Draft test at {}'.format(datetime.utcnow()),
        'body': '<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>',
        'to': [{'name': 'The red-haired mermaid',
                'email': account.email_address}]
    }


@pytest.fixture(scope='function')
def attachments(db):
    from inbox.models import Block
    test_data = [('muir.jpg', 'image/jpeg'),
                 ('LetMeSendYouEmail.wav', 'audio/vnd.wave'),
                 ('first-attachment.jpg', 'image/jpeg')]

    new_attachments = []
    for filename, content_type in test_data:

        test_attachment_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'data', filename)

        with open(test_attachment_path, 'r') as f:
            b = Block(namespace_id=NAMESPACE_ID,
                      filename=filename,
                      data=f.read())
            # for now because of lousy _content_type enum
            b.content_type = content_type
            db.session.add(b)
            db.session.commit()
            new_attachments.append(b.public_id)

    return new_attachments


def test_create_and_get_draft(api_client, example_draft):
    r = api_client.post_data('/drafts', example_draft)
    public_id = json.loads(r.data)['id']
    assert r.status_code == 200

    r = api_client.get_data('/drafts')
    matching_saved_drafts = [draft for draft in r if draft['id'] == public_id]
    assert len(matching_saved_drafts) == 1
    saved_draft = matching_saved_drafts[0]
    assert saved_draft['state'] == 'draft'
    assert all(saved_draft[k] == v for k, v in example_draft.iteritems())

    # Check that thread gets the draft tag
    threads_with_drafts = api_client.get_data('/threads?tag=drafts')
    assert len(threads_with_drafts) == 1


def test_create_reply_draft(api_client):
    thread_public_id = api_client.get_data('/threads')[0]['id']

    reply_draft = {
        'subject': 'test reply',
        'body': 'test reply',
        'reply_to_thread': thread_public_id
    }
    r = api_client.post_data('/drafts', reply_draft)
    draft_public_id = json.loads(r.data)['id']

    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 1
    assert drafts[0]['state'] == 'draft'

    assert thread_public_id == drafts[0]['thread']

    thread_data = api_client.get_data('/threads/{}'.format(thread_public_id))
    assert draft_public_id in thread_data['drafts']


def test_drafts_filter(api_client, example_draft):
    r = api_client.post_data('/drafts', example_draft)
    public_id = json.loads(r.data)['id']

    r = api_client.get_data('/drafts')
    matching_saved_drafts = [draft for draft in r if draft['id'] == public_id]
    thread_public_id = matching_saved_drafts[0]['thread']

    reply_draft = {
        'subject': 'test reply',
        'body': 'test reply',
        'reply_to_thread': thread_public_id
    }
    r = api_client.post_data('/drafts', reply_draft)

    results = api_client.get_data('/drafts?thread={}'.format(thread_public_id))
    assert len(results) == 2


def test_create_draft_with_attachments(api_client, attachments):
    # TODO(emfree)
    pass


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

    updated_draft = {
        'subject': 'updated draft',
        'body': 'updated draft',
    }

    r = api_client.post_data('/drafts/{}'.format(draft_public_id),
                             updated_draft)
    updated_public_id = json.loads(r.data)['id']

    assert updated_public_id != draft_public_id
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

    updated_draft = {
        'subject': 'updated draft',
        'body': 'updated draft'
    }
    r = api_client.post_data('/drafts/{}'.format(draft_public_id),
                             updated_draft)
    updated_public_id = json.loads(r.data)['id']

    r = api_client.delete('/drafts/{}'.format(updated_public_id))

    # Check that drafts were deleted
    drafts = api_client.get_data('/drafts')
    assert not drafts


def test_send(patch_network_functions, api_client, example_draft,
              syncback_service):
    r = api_client.post_data('/drafts', example_draft)
    draft_public_id = json.loads(r.data)['id']

    r = api_client.post_data('/send', {'draft_id': draft_public_id})

    # TODO(emfree) do this more rigorously
    gevent.sleep(2)

    drafts = api_client.get_data('/drafts')
    threads_with_drafts = api_client.get_data('/threads?tag=drafts')
    assert not drafts
    assert not threads_with_drafts

    sent_threads = api_client.get_data('/threads?tag=sent')
    assert len(sent_threads) == 1

    message = api_client.get_data('/messages/{}'.format(draft_public_id))
    assert message['state'] == 'sent'
    assert message['object'] == 'message'


def test_conflicting_updates(api_client):
    original_draft = {
        'subject': 'parent draft',
        'body': 'parent draft'
    }
    r = api_client.post_data('/drafts', original_draft)
    original_public_id = json.loads(r.data)['id']

    updated_draft = {
        'subject': 'updated draft',
        'body': 'updated draft'
    }
    r = api_client.post_data('/drafts/{}'.format(original_public_id),
                             updated_draft)
    assert r.status_code == 200
    updated_public_id = json.loads(r.data)['id']

    conflicting_draft = {
        'subject': 'conflicting draft',
        'body': 'conflicting draft'
    }
    r = api_client.post_data('/drafts/{}'.format(original_public_id),
                             conflicting_draft)
    assert r.status_code == 409

    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 1
    assert drafts[0]['id'] == updated_public_id


def test_update_to_nonexistent_draft(api_client):
    updated_draft = {
        'subject': 'updated draft',
        'body': 'updated draft'
    }

    r = api_client.post_data('/drafts/{}'.format('notarealid'), updated_draft)
    assert r.status_code == 404
    drafts = api_client.get_data('/drafts')
    assert len(drafts) == 0
