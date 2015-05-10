from tests.util.base import api_client, add_fake_thread

from tests.general.test_message_parsing import (new_message_from_synced,
                                                raw_message)
from tests.util.base import default_namespace

__all__ = ['api_client', 'new_message_from_synced', 'default_namespace']


def test_rfc822_format(db, api_client, new_message_from_synced):
    """ Test the API response to retreive raw message contents """
    NAMESPACE_ID = default_namespace(db).id
    new_msg = new_message_from_synced
    fake_thread = add_fake_thread(db.session, NAMESPACE_ID)
    new_msg.thread = fake_thread
    db.session.add_all([new_msg, fake_thread])
    db.session.commit()

    full_path = api_client.full_path('/messages/{}'.format(new_msg.public_id))

    results = api_client.client.get(full_path,
                                    headers={'Accept': 'message/rfc822'})

    assert results.data == raw_message()
