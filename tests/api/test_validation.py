# -*- coding: utf-8 -*-
import json
from inbox.models import Namespace
from inbox.api.validation import noop_event_update, valid_email
from tests.util.base import db, calendar, add_fake_event
from tests.api.base import api_client

__all__ = ['api_client', 'db', 'calendar']


# TODO(emfree): Add more comprehensive parameter-validation tests.


def test_account_validation(api_client, db, default_namespace):

    draft = {
        'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>'
    }

    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 200

    namespace_id = json.loads(r.data)['account_id']
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


def test_valid_email():
    assert valid_email('karim@nylas.com') is True
    assert valid_email('karim nylas.com') is False
    # We want email addresses, not full addresses
    assert valid_email('Helena Handbasket <helena@nylas.com>') is False
    assert valid_email('le roi de la montagne') is False
    assert valid_email('le roi de la montagne@example.com') is False
    assert valid_email('le-roi-de-la-montagne@example.com') is True
    assert valid_email('le_roi_de_la_montagne@example.com') is True
    assert valid_email('spaces with@example.com') is False
