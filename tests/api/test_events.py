import os
import json

from inbox.sqlalchemy_ext.util import generate_public_id
from inbox.models import Account
from tests.util.base import api_client

__all__ = ['api_client']


ACCOUNT_ID = 1


def test_api_list(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {'subject': 'subj', 'body': 'body1',
              'when': {'time': 1}, 'location': 'InboxHQ'}
    e_data2 = {'subject': 'subj2', 'body': 'body2',
               'when': {'time': 1}, 'location': 'InboxHQ'}
    api_client.post_data('/events', e_data, ns_id)
    api_client.post_data('/events', e_data2, ns_id)

    event_list = api_client.get_data('/events', ns_id)
    event_subjects = [event['subject'] for event in event_list]
    assert 'subj' in event_subjects
    assert 'subj2' in event_subjects

    event_bodies = [event['body'] for event in event_list]
    assert 'body1' in event_bodies
    assert 'body2' in event_bodies


def test_api_get(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {'subject': 'subj', 'when': {'time': 1}, 'location': 'InboxHQ'}
    e_data2 = {'subject': 'subj2', 'when': {'time': 1}, 'location': 'InboxHQ'}
    api_client.post_data('/events', e_data, ns_id)
    api_client.post_data('/events', e_data2, ns_id)

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


def test_api_create(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': 'Friday Office Party',
        'when': {'time': 1407542195},
        'location': 'Inbox HQ',
    }

    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['namespace_id'] == acct.namespace.public_id
    assert e_resp_data['subject'] == e_data['subject']
    assert e_resp_data['location'] == e_data['location']
    assert e_resp_data['when']['time'] == e_data['when']['time']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']
    e_get_resp = api_client.get_data('/events/' + e_id, ns_id)

    assert e_get_resp['object'] == 'event'
    assert e_get_resp['namespace_id'] == acct.namespace.public_id
    assert e_get_resp['id'] == e_id
    assert e_get_resp['subject'] == e_data['subject']
    assert e_get_resp['when']['time'] == e_data['when']['time']


def test_api_create_ical(db, api_client):
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
    assert e_resp_data['namespace_id'] == acct.namespace.public_id
    assert e_resp_data['subject'] == 'test recurring event'
    assert e_resp_data['body'] == 'Event Discription'
    assert e_resp_data['location'] == 'just some location'
    assert e_resp_data['when']['object'] == 'datespan'
    assert e_resp_data['when']['start_date'] == '2014-08-10'
    assert e_resp_data['when']['end_date'] == '2014-08-11'
    part_names = [p['name'] for p in e_resp_data['participants']]
    assert 'John Q. Public' in part_names
    assert 'Alyssa P Hacker' in part_names
    assert 'benbitdit@example.com' in part_names
    assert 'Filet Minyon' in part_names
    for p in e_resp_data['participants']:
        if p['name'] == 'John Q. Public':
            assert p['status'] == 'noreply'
            assert p['email'] == 'johnqpublic@example.com'
        if p['name'] == 'Alyssa P Hacker':
            assert p['status'] == 'yes'
            assert p['email'] == 'alyssaphacker@example.com'
        if p['name'] == 'benbitdit@example.com':
            assert p['status'] == 'no'
            assert p['email'] == 'benbitdit@example.com'
        if p['name'] == 'Filet Minyon':
            assert p['status'] == 'maybe'
            assert p['email'] == 'filet.minyon@example.com'


def test_api_create_no_subject(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': '',
        'when': {'time': 1407542195},
    }

    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['namespace_id'] == acct.namespace.public_id
    assert e_resp_data['subject'] == e_data['subject']
    assert e_resp_data['when']['time'] == e_data['when']['time']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']
    e_get_resp = api_client.get_data('/events/' + e_id, ns_id)

    assert e_get_resp['object'] == 'event'
    assert e_get_resp['namespace_id'] == acct.namespace.public_id
    assert e_get_resp['id'] == e_id
    assert e_get_resp['subject'] == e_data['subject']
    assert e_get_resp['when']['time'] == e_data['when']['time']


def test_api_update_subject(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': '',
        'when': {'time': 1407542195},
    }

    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['namespace_id'] == acct.namespace.public_id
    assert e_resp_data['subject'] == e_data['subject']
    assert e_resp_data['when']['time'] == e_data['when']['time']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']

    e_update_data = {'subject': 'new subject'}
    e_put_resp = api_client.put_data('/events/' + e_id, e_update_data, ns_id)
    e_put_data = json.loads(e_put_resp.data)

    assert e_put_data['object'] == 'event'
    assert e_put_data['namespace_id'] == acct.namespace.public_id
    assert e_put_data['id'] == e_id
    assert e_put_data['subject'] == 'new subject'
    assert e_put_data['when']['object'] == 'time'
    assert e_put_data['when']['time'] == e_data['when']['time']


def test_api_update_invalid(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    e_update_data = {'subject': 'new subject'}
    e_id = generate_public_id()
    e_put_resp = api_client.put_data('/events/' + e_id, e_update_data, ns_id)
    assert e_put_resp.status_code != 200


def test_api_create_ical_invalid(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    headers = {'content-type': 'text/calendar'}
    e_resp = api_client.post_raw('/events', 'asdf', ns_id, headers=headers)
    assert e_resp.status_code != 200


def test_api_delete(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'subject': '',
        'when': {'time': 1407542195},
    }

    e_resp = api_client.post_data('/events', e_data, ns_id)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['namespace'] == acct.namespace.public_id
    assert e_resp_data['subject'] == e_data['subject']
    assert e_resp_data['when']['time'] == e_data['when']['time']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']

    api_client.delete('/events/' + e_id, ns_id=ns_id)

    event = api_client.get_data('/events/' + e_id, ns_id)
    assert event['type'] == 'invalid_request_error'


def test_api_delete_invalid(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_id = 'asdf'
    resp = api_client.delete('/events/' + e_id, ns_id=ns_id)
    assert resp.status_code != 200

    e_id = generate_public_id()
    resp = api_client.delete('/events/' + e_id, ns_id=ns_id)
    assert resp.status_code != 200
