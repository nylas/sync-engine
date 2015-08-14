# -*- coding: utf-8 -*-
import json
from inbox.models import Namespace
from inbox.sqlalchemy_ext.util import generate_public_id
from inbox.api.validation import noop_event_update
from tests.util.base import db, calendar, add_fake_event
from tests.api_legacy.base import api_client

__all__ = ['api_client', 'db', 'calendar']


def test_namespace_id_validation(api_client, db, default_namespace):
    actual_namespace_id, = db.session.query(Namespace.public_id).first()
    r = api_client.client.get('/n/{}'.format(actual_namespace_id))
    assert r.status_code == 200

    fake_namespace_id = generate_public_id()
    r = api_client.client.get('/n/{}'.format(fake_namespace_id))
    assert r.status_code == 404

    malformed_namespace_id = 'this string is definitely not base36-decodable'
    r = api_client.client.get('/n/{}'.format(malformed_namespace_id))
    assert r.status_code == 400


# TODO(emfree): Add more comprehensive parameter-validation tests.


def test_account_validation(api_client, db, default_namespace):

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


def test_noop_event_update(db, default_namespace, calendar):
    event = add_fake_event(db.session, default_namespace.id,
                           calendar=calendar,
                           read_only=True)

    event.title = 'Test event'
    event.participants = [{'email': 'helena@nylas.com'},
                          {'email': 'benb@nylas.com'}]

    assert noop_event_update(event, {}) is True

    update = {'title': 'Test event'}
    assert noop_event_update(event, update) is True

    update = {'title': 'Different'}
    assert noop_event_update(event, update) is False

    update = {'location': 'Different'}
    assert noop_event_update(event, update) is False

    update = {'description': 'Different'}
    assert noop_event_update(event, update) is False

    update = {'when': {'start_time': 123453453, 'end_time': 1231231}}
    assert noop_event_update(event, update) is False

    event.when = {'start_time': 123453453, 'end_time': 1231231}
    update = {'when': {'start_time': 123453453, 'end_time': 1231231}}
    assert noop_event_update(event, update) is True

    update = {'participants': [{'email': 'benb@nylas.com'},
                               {'email': 'helena@nylas.com'}]}
    assert noop_event_update(event, update) is True

    update = {'participants': [{'email': 'benb@nylas.com', 'status': 'yes'},
                               {'email': 'helena@nylas.com'}]}
    assert noop_event_update(event, update) is False

    event.participants = [{'email': 'benb@nylas.com', 'status': 'yes'},
                          {'email': 'helena@nylas.com'}]
    update = {'participants': [{'email': 'benb@nylas.com', 'status': 'yes'},
                               {'email': 'helena@nylas.com'}]}
    assert noop_event_update(event, update) is True
