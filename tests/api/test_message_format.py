from tests.util.base import (api_client, add_fake_thread,
                             new_message_from_synced)

__all__ = ['api_client', 'new_message_from_synced']


def test_rfc822_format(db, api_client, default_namespace, raw_message):
    """ Test the API response to retreive raw message contents """
    namespace_id = default_namespace.id
    new_msg = new_message_from_synced(db, default_namespace.account, raw_message)
    fake_thread = add_fake_thread(db.session, namespace_id)
    new_msg.thread = fake_thread
    db.session.add_all([new_msg, fake_thread])
    db.session.commit()

    full_path = api_client.full_path('/messages/{}'.format(new_msg.public_id))

    results = api_client.client.get(full_path,
                                    headers={'Accept': 'message/rfc822'})

    assert results.data == raw_message
