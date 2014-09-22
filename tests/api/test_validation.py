import json

from inbox.sqlalchemy_ext.util import generate_public_id
from tests.util.base import api_client


def test_namespace_id_validation(api_client, db):
    from inbox.models import Namespace
    actual_namespace_id, = db.session.query(Namespace.public_id).first()
    r = api_client.client.get('/n/{}'.format(actual_namespace_id))
    assert r.status_code == 200

    fake_namespace_id = generate_public_id()
    r = api_client.client.get('/n/{}'.format(fake_namespace_id))
    assert r.status_code == 404

    malformed_namespace_id = 'this string is definitely not base36-decodable'
    r = api_client.client.get('/n/{}'.format(malformed_namespace_id))
    assert r.status_code == 404


def test_recipient_validation(api_client):
    r = api_client.post_data('/drafts', {'to': [{'email': 'foo@example.com'}]})
    assert r.status_code == 200
    r = api_client.post_data('/drafts', {'to': {'email': 'foo@example.com'}})
    assert r.status_code == 400
    r = api_client.post_data('/drafts', {'to': 'foo@example.com'})
    assert r.status_code == 400
    r = api_client.post_data('/drafts', {'to': [{'name': 'foo'}]})
    assert r.status_code == 400
    r = api_client.post_data('/send', {'to': [{'email': 'foo'}]})
    assert r.status_code == 400
    r = api_client.post_data('/drafts', {'to': [{'email': ['foo']}]})
    assert r.status_code == 400
    r = api_client.post_data('/drafts', {'to': [{'name': ['Mr. Foo'],
                                                 'email': 'foo@example.com'}]})
    assert r.status_code == 400
    r = api_client.post_data('/drafts',
                             {'to': [{'name': 'Good Recipient',
                                      'email': 'goodrecipient@example.com'},
                                     'badrecipient@example.com']})
    assert r.status_code == 400

# TODO(emfree): Add more comprehensive parameter-validation tests.


def test_account_validation(api_client, db):
    from inbox.models import Namespace

    draft = {
        'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>'
    }

    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 200

    namespace_id = json.loads(r.data)['namespace_id']
    account = db.session.query(Namespace).filter(
        Namespace.public_id == namespace_id).first().account

    account.sync_state = 'invalid'
    db.session.commit()

    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 403

    account.sync_state = 'connerror'
    db.session.commit()

    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 503
