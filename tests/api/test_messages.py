import pytest
import json

from inbox.util.blockstore import get_from_blockstore

from tests.util.base import (add_fake_message, default_namespace,
                             new_message_from_synced, mime_message, thread,
                             add_fake_thread, generic_account, gmail_account)
from tests.api.base import api_client, new_api_client


__all__ = ['api_client', 'default_namespace', 'new_message_from_synced',
           'mime_message', 'thread', 'generic_account', 'gmail_account']


@pytest.fixture(params=['/messages', '/messages2'])
def messages_endpoint(request):
    return request.param


@pytest.fixture(params=['/threads', '/threads2'])
def threads_endpoint(request):
    return request.param


@pytest.fixture
def stub_message_from_raw(db, thread, new_message_from_synced):
    new_msg = new_message_from_synced
    new_msg.thread = thread
    db.session.add(new_msg)
    db.session.commit()
    return new_msg


@pytest.fixture
def stub_message(db, new_message_from_synced, default_namespace, thread):
    message = add_fake_message(db.session, default_namespace.id, thread,
                               subject="Golden Gate Park next Sat",
                               from_addr=[('alice', 'alice@example.com')],
                               to_addr=[('bob', 'bob@example.com')])
    message.snippet = 'Banh mi paleo pickled, sriracha'
    message.body = """
Banh mi paleo pickled, sriracha biodiesel chambray seitan
mumblecore mustache. Raw denim gastropub 8-bit, butcher
PBR sartorial photo booth Pinterest blog Portland roof party
cliche bitters aesthetic. Ugh.
"""

    message = add_fake_message(db.session, default_namespace.id, thread,
                               subject="Re:Golden Gate Park next Sat",
                               from_addr=[('bob', 'bob@example.com')],
                               to_addr=[('alice', 'alice@example.com')],
                               cc_addr=[('Cheryl', 'cheryl@gmail.com')])
    message.snippet = 'Bushwick meggings ethical keffiyeh'
    message.body = """
Bushwick meggings ethical keffiyeh. Chambray lumbersexual wayfarers,
irony Banksy cred bicycle rights scenester artisan tote bag YOLO gastropub.
"""

    draft = add_fake_message(db.session, default_namespace.id, thread,
                             subject="Re:Golden Gate Park next Sat",
                             from_addr=[('alice', 'alice@example.com')],
                             to_addr=[('bob', 'bob@example.com')],
                             cc_addr=[('Cheryl', 'cheryl@gmail.com')])
    draft.snippet = 'Hey there friend writing a draft'
    draft.body = """
DIY tousled Tumblr, VHS meditation 3 wolf moon listicle fingerstache viral
bicycle rights. Thundercats kale chips church-key American Apparel.
"""
    draft.is_draft = True
    draft.reply_to_message = message

    db.session.commit()
    return message


# TODO(emfree) clean up fixture dependencies
def test_rfc822_format(stub_message_from_raw, api_client, messages_endpoint, mime_message):
    """ Test the API response to retreive raw message contents """
    full_path = messages_endpoint + '/{}'.format(stub_message_from_raw.public_id)

    resp = api_client.get_raw(full_path,
                            headers={'Accept': 'message/rfc822'})
    assert resp.data == get_from_blockstore(stub_message_from_raw.data_sha256)


def test_sender_and_participants(stub_message, api_client, threads_endpoint):
    resp = api_client.get_raw(threads_endpoint + '/{}'
                              .format(stub_message.thread.public_id))
    assert resp.status_code == 200
    resp_dict = json.loads(resp.data)
    participants = resp_dict['participants']
    assert len(participants) == 3

    # Not expanded, should only return IDs
    assert 'message' not in resp_dict
    assert 'drafts' not in resp_dict


@pytest.mark.xfail # Not counting drafts as messages
def test_expanded_threads(stub_message, api_client, threads_endpoint):
    def _check_json_thread(resp_dict):
        assert 'message_ids' not in resp_dict
        assert 'messages' in resp_dict
        assert 'drafts' in resp_dict

        assert len(resp_dict['participants']) == 3
        assert len(resp_dict['messages']) == 2
        assert len(resp_dict['drafts']) == 1

        for msg_dict in resp_dict['messages']:
            assert 'body' not in msg_dict
            assert msg_dict['object'] == 'message'
            assert msg_dict['thread_id'] == stub_message.thread.public_id
            valid_keys = ['account_id', 'to', 'from', 'files', 'unread',
                          'unread', 'date', 'snippet']
            assert all(x in msg_dict for x in valid_keys)

        for draft in resp_dict['drafts']:
            assert 'body' not in draft
            assert draft['object'] == 'draft'
            assert draft['thread_id'] == stub_message.thread.public_id
            valid_keys = ['account_id', 'to', 'from', 'files', 'unread',
                          'snippet', 'date', 'version', 'reply_to_message_id']
            assert all(x in draft for x in valid_keys)

    # /threads/<thread_id>
    resp = api_client.get_raw(
        threads_endpoint + '/{}?view=expanded'.format(stub_message.thread.public_id))
    assert resp.status_code == 200
    resp_dict = json.loads(resp.data)
    _check_json_thread(resp_dict)

    # /threads/
    resp = api_client.get_raw(
        threads_endpoint + '/?view=expanded'.format(stub_message.thread.public_id))
    assert resp.status_code == 200
    resp_dict = json.loads(resp.data)

    for thread_json in resp_dict:
        if thread_json['id'] == stub_message.thread.public_id:
            _check_json_thread(thread_json)


def test_expanded_message(stub_message, api_client, messages_endpoint):
    def _check_json_message(msg_dict):
        assert 'body' in msg_dict
        assert msg_dict['object'] == 'message'
        assert msg_dict['thread_id'] == stub_message.thread.public_id

        assert isinstance(msg_dict['headers'], dict)
        assert 'In-Reply-To' in msg_dict['headers']
        assert 'References' in msg_dict['headers']
        assert 'Message-Id' in msg_dict['headers']

        valid_keys = ['account_id', 'to', 'from', 'files', 'unread',
                      'unread', 'date', 'snippet']
        assert all(x in msg_dict for x in valid_keys)

    # /message/<message_id>
    resp = api_client.get_raw(
        messages_endpoint + '/{}?view=expanded'.format(stub_message.public_id))
    assert resp.status_code == 200
    resp_dict = json.loads(resp.data)
    _check_json_message(resp_dict)

    # /messages/
    resp = api_client.get_raw(messages_endpoint + '/?view=expanded')
    assert resp.status_code == 200
    resp_dict = json.loads(resp.data)

    for message_json in resp_dict:
        if message_json['id'] == stub_message.public_id:
            _check_json_message(message_json)


def test_message_folders(db, generic_account, threads_endpoint, messages_endpoint):
    # Because we're using the generic_account namespace
    api_client = new_api_client(db, generic_account.namespace)

    # Generic IMAP threads, messages have a 'folders' field
    generic_thread = add_fake_thread(db.session, generic_account.namespace.id)
    generic_message = add_fake_message(db.session,
                                       generic_account.namespace.id,
                                       generic_thread)

    resp_data = api_client.get_data(
        threads_endpoint + '/{}'.format(generic_thread.public_id))

    assert resp_data['id'] == generic_thread.public_id
    assert resp_data['object'] == 'thread'
    assert 'folders' in resp_data and 'labels' not in resp_data

    resp_data = api_client.get_data(
        messages_endpoint + '/{}'.format(generic_message.public_id))

    assert resp_data['id'] == generic_message.public_id
    assert resp_data['object'] == 'message'
    assert 'folder' in resp_data and 'labels' not in resp_data


def test_message_labels(db, gmail_account, threads_endpoint, messages_endpoint):
    # Because we're using the gmail_account namespace
    api_client = new_api_client(db, gmail_account.namespace)

    # Gmail threads, messages have a 'labels' field
    gmail_thread = add_fake_thread(db.session, gmail_account.namespace.id)
    gmail_message = add_fake_message(db.session,
                                     gmail_account.namespace.id, gmail_thread)

    resp_data = api_client.get_data(
        threads_endpoint + '/{}'.format(gmail_thread.public_id))

    assert resp_data['id'] == gmail_thread.public_id
    assert resp_data['object'] == 'thread'
    assert 'labels' in resp_data and 'folders' not in resp_data

    resp_data = api_client.get_data(
        messages_endpoint + '/{}'.format(gmail_message.public_id))

    assert resp_data['id'] == gmail_message.public_id
    assert resp_data['object'] == 'message'
    assert 'labels' in resp_data and 'folders' not in resp_data
