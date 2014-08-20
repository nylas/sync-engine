import os
import json

from inbox.models import Account
from tests.util.base import (event_sync, events_provider,
                             api_client)

__all__ = ['events_provider', 'event_sync', 'api_client']


ACCOUNT_ID = 1


def test_api_list(events_provider, event_sync, db, api_client):
    events_provider.supply_event('subj', 'body1', 0, 1, False, False)
    events_provider.supply_event('subj2', 'body2', 0, 1, False, False)

    event_sync.provider_instance = events_provider
    event_sync.poll()
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    event_list = api_client.get_data('/events', ns_id)
    event_subjects = [event['subject'] for event in event_list]
    assert 'subj' in event_subjects
    assert 'subj2' in event_subjects

    event_bodies = [event['body'] for event in event_list]
    assert 'body1' in event_bodies
    assert 'body2' in event_bodies


def test_api_get(events_provider, event_sync, db, api_client):
    events_provider.supply_event('subj', '', 0, 1, False, False)
    events_provider.supply_event('subj2', '', 0, 1, False, False)

    event_sync.provider_instance = events_provider
    event_sync.poll()
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    event_list = api_client.get_data('/events', ns_id)

    event_ids = [event['id'] for event in event_list]

    c1found = False
    c2found = False
    for c_id in event_ids:
        event = api_client.get_data('/events/' + c_id, ns_id)

        if event['subject'] == 'subj':
            c1found = True

        if event['subject'] == 'subj2':
            c2found = True

    assert c1found
    assert c2found


def test_api_create(events_provider, event_sync, db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': 'Friday Office Party',
        'start': 1407542195,
        'end': 1407543195,
        'busy': False,
        'all_day': False
    }

    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['namespace'] == acct.namespace.public_id
    assert e_resp_data['subject'] == e_data['subject']
    assert e_resp_data['start'] == e_data['start']
    assert e_resp_data['end'] == e_data['end']
    assert e_resp_data['busy'] == e_data['busy']
    assert e_resp_data['all_day'] == e_data['all_day']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']
    e_get_resp = api_client.get_data('/events/' + e_id, ns_id)

    assert e_get_resp['object'] == 'event'
    assert e_get_resp['namespace'] == acct.namespace.public_id
    assert e_get_resp['id'] == e_id
    assert e_get_resp['subject'] == e_data['subject']
    assert e_get_resp['start'] == e_data['start']
    assert e_get_resp['end'] == e_data['end']
    assert e_get_resp['busy'] == e_data['busy']
    assert e_get_resp['all_day'] == e_data['all_day']


def test_api_create_ical(events_provider, event_sync, db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    tests_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                              '..')
    invite_path = os.path.join(tests_path, 'data', 'invite.ics')
    f = open(invite_path, 'r')
    cal_str = f.read()
    f.close()

    headers = {'content-type': 'text/calendar'}
    e_resp = api_client.post_raw('/events', cal_str, ns_id, headers=headers)
    e_resp_data = json.loads(e_resp.data)[0]
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['namespace'] == acct.namespace.public_id
    assert e_resp_data['subject'] == 'test recurring event'
    assert e_resp_data['body'] == 'Event Discription'
    assert e_resp_data['location'] == 'just some location'
    assert e_resp_data['start'] == 1407628800
    assert e_resp_data['end'] == 1407715200
    assert e_resp_data['busy'] is True
    assert e_resp_data['all_day'] is True
    part_names = [p['name'] for p in e_resp_data['participants']]
    assert 'John Q. Public' in part_names
    assert 'Alyssa P Hacker' in part_names
    assert 'benbitdit@example.com' in part_names
    assert 'Filet Minyon' in part_names
    for p in e_resp_data['participants']:
        if p['name'] == 'John Q. Public':
            assert p['status'] == 'awaiting'
            assert p['email'] == 'johnqpublic@example.com'
        if p['name'] == 'Alyssa P Hacker':
            assert p['notes'] == 'Guests: 1'
            assert p['status'] == 'yes'
            assert p['email'] == 'alyssaphacker@example.com'
        if p['name'] == 'benbitdit@example.com':
            assert p['status'] == 'no'
            assert p['email'] == 'benbitdit@example.com'
        if p['name'] == 'Filet Minyon':
            assert p['status'] == 'maybe'
            assert p['email'] == 'filet.minyon@example.com'


def test_api_create_no_subject(events_provider, event_sync, db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': '',
        'start': 1407542195,
        'end': 1407543195,
        'busy': False,
        'all_day': False
    }

    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['namespace'] == acct.namespace.public_id
    assert e_resp_data['subject'] == e_data['subject']
    assert e_resp_data['start'] == e_data['start']
    assert e_resp_data['end'] == e_data['end']
    assert e_resp_data['busy'] == e_data['busy']
    assert e_resp_data['all_day'] == e_data['all_day']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']
    e_get_resp = api_client.get_data('/events/' + e_id, ns_id)

    assert e_get_resp['object'] == 'event'
    assert e_get_resp['namespace'] == acct.namespace.public_id
    assert e_get_resp['id'] == e_id
    assert e_get_resp['subject'] == e_data['subject']
    assert e_get_resp['start'] == e_data['start']
    assert e_get_resp['end'] == e_data['end']
    assert e_get_resp['busy'] == e_data['busy']
    assert e_get_resp['all_day'] == e_data['all_day']


def test_create_start_after_end(events_provider, event_sync, db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': 'Friday Office Party',
        'start': 1407543195,
        'end': 1407542195,
        'busy': False,
        'all_day': False
    }

    event_list = api_client.get_data('/events', ns_id)
    length_before = len(event_list)
    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)

    assert e_resp_data["type"] == "invalid_request_error"

    event_list = api_client.get_data('/events', ns_id)
    length_after = len(event_list)
    assert length_before == length_after


def test_create_nonbool_busy(events_provider, event_sync, db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': '',
        'start': -1407543195,
        'end': 1407542195,
        'busy': 'yes',
        'all_day': False
    }

    event_list = api_client.get_data('/events', ns_id)
    length_before = len(event_list)
    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)

    assert e_resp_data["type"] == "invalid_request_error"

    event_list = api_client.get_data('/events', ns_id)
    length_after = len(event_list)
    assert length_before == length_after


def test_create_nonbool_all_day(events_provider, event_sync, db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': '',
        'start': -1407543195,
        'end': 1407542195,
        'busy': True,
        'all_day': 'False'
    }

    event_list = api_client.get_data('/events', ns_id)
    length_before = len(event_list)
    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)

    assert e_resp_data["type"] == "invalid_request_error"

    event_list = api_client.get_data('/events', ns_id)
    length_after = len(event_list)
    assert length_before == length_after
