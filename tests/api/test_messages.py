import pytest
import json
from tests.util.base import api_client, add_fake_thread

from tests.general.test_message_parsing import (new_message_from_synced,
                                                raw_message)
from tests.util.base import default_namespace

__all__ = ['api_client', 'new_message_from_synced', 'default_namespace']


@pytest.fixture
def stub_message(db, new_message_from_synced):
    NAMESPACE_ID = default_namespace(db).id
    new_msg = new_message_from_synced
    fake_thread = add_fake_thread(db.session, NAMESPACE_ID)
    new_msg.thread = fake_thread
    db.session.add_all([new_msg, fake_thread])
    db.session.commit()
    return new_msg


def test_rfc822_format(stub_message, api_client):
    """ Test the API response to retreive raw message contents """
    full_path = api_client.full_path('/messages/{}'.format(
        stub_message.public_id), ns_id=stub_message.namespace_id)

    results = api_client.client.get(full_path,
                                    headers={'Accept': 'message/rfc822'})
    assert results.data == raw_message()


def test_sender_and_participants(stub_message, api_client):
    resp = api_client.client.get(api_client.full_path(
        '/threads/{}'.format(stub_message.thread.public_id),
        ns_id=stub_message.namespace_id))
    assert resp.status_code == 200
    resp_dict = json.loads(resp.data)
    senders = resp_dict['senders']
    assert len(senders) == 1
    sender = senders[0]
    assert sender['email'] == 'tp@ai.mit.edu'
    assert sender['name'] == 'Tomaso Poggio'

    participants = resp_dict['participants']
    assert len(participants) == 4
