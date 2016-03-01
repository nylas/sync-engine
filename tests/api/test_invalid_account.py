import datetime
import json
import mock

import pytest
import requests

from tests.util.base import db
from tests.api.base import api_client

__all__ = ['api_client', 'db']


@pytest.fixture
def token_manager(monkeypatch):
    monkeypatch.setattr(
        'inbox.models.backends.gmail.g_token_manager.get_token_for_email',
        lambda *args, **kwargs: 'token')


@pytest.fixture
def search_response():
    resp = requests.Response()
    resp.status_code = 200
    resp.elapsed = datetime.timedelta(seconds=22)
    resp._content = json.dumps({
        'messages': [{'id': '1'}, {'id': '2'}, {'id': '3'}]
    })
    requests.get = mock.Mock(return_value=resp)


@pytest.fixture
def setup_account(message, thread, label, contact, event):
    return {
        'message': message.public_id,
        'thread': thread.public_id,
        'label': label.category.public_id,
        'contact': contact.public_id,
        'event': event.public_id
    }


def test_read_endpoints(db, setup_account, api_client, default_account):
    # Read operations succeed.
    for resource, public_id in setup_account.items():
        endpoint = '/{}s'.format(resource)
        r = api_client.get_raw(endpoint)
        assert r.status_code == 200

        read_endpoint = '{}/{}'.format(endpoint, public_id)
        r = api_client.get_raw(read_endpoint)
        assert r.status_code == 200

    default_account.sync_state = 'invalid'
    db.session.commit()

    # Read operations on an invalid account also succeed.
    for resource, public_id in setup_account.items():
        endpoint = '/{}s'.format(resource)
        r = api_client.get_raw(endpoint)
        assert r.status_code == 200

        read_endpoint = '{}/{}'.format(endpoint, public_id)
        r = api_client.get_raw(read_endpoint)
        assert r.status_code == 200


def test_search_endpoints(db, api_client, token_manager, search_response,
                          default_account):
    # Message, thread search succeeds.
    for endpoint in ('messages', 'threads'):
        r = api_client.get_raw('/{}/search?q=queryme'.format(endpoint))
        assert r.status_code == 200

    default_account.sync_state = 'invalid'
    db.session.commit()

    # Message, thread search on an invalid account fails with an HTTP 403.
    for endpoint in ('messages', 'threads'):
        r = api_client.get_raw('/{}/search?q=queryme'.format(endpoint))
        assert r.status_code == 403


def test_write_endpoints(db, setup_account, api_client, default_account):
    # Write operations (create, update, delete) succeed.
    r = api_client.post_data(
        '/drafts',
        data={
            'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>'
        })
    assert r.status_code == 200
    draft_id = json.loads(r.data)['id']

    endpoint = '/messages/{}'.format(setup_account['message'])
    r = api_client.put_data(endpoint, data={"starred": True})
    assert r.status_code == 200

    endpoint = '/events/{}'.format(setup_account['event'])
    r = api_client.delete(endpoint)
    assert r.status_code == 200

    default_account.sync_state = 'invalid'
    db.session.commit()

    # Write operations fail with an HTTP 403.
    r = api_client.post_data('/labels', data={"display_name": "Neu!"})
    assert r.status_code == 403

    endpoint = '/threads/{}'.format(setup_account['thread'])
    r = api_client.put_data(endpoint, data={"starred": True})
    assert r.status_code == 403

    endpoint = '/drafts/{}'.format(draft_id)
    r = api_client.delete(endpoint)
    assert r.status_code == 403
