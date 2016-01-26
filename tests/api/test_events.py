import json

from inbox.sqlalchemy_ext.util import generate_public_id
from inbox.models import Event, Calendar
from tests.util.base import db, calendar, add_fake_event
from tests.api.base import api_client

__all__ = ['api_client', 'calendar', 'db']


def test_create_event(db, api_client, calendar):
    e_data = {'title': 'subj', 'description': 'body1',
              'calendar_id': calendar.public_id,
              'when': {'time': 1}, 'location': 'InboxHQ'}
    e_data2 = {'title': 'subj2', 'description': 'body2',
               'calendar_id': calendar.public_id,
               'when': {'time': 1}, 'location': 'InboxHQ'}
    api_client.post_data('/events', e_data)
    api_client.post_data('/events', e_data2)
    db.session.commit()


def test_api_list(db, api_client, calendar):
    e_data = {'title': 'subj', 'description': 'body1',
              'calendar_id': calendar.public_id,
              'when': {'time': 1}, 'location': 'InboxHQ'}
    e_data2 = {'title': 'subj2', 'description': 'body2',
               'calendar_id': calendar.public_id,
               'when': {'time': 1}, 'location': 'InboxHQ'}
    api_client.post_data('/events', e_data)
    api_client.post_data('/events', e_data2)

    event_list = api_client.get_data('/events')
    event_titles = [event['title'] for event in event_list]
    assert 'subj' in event_titles
    assert 'subj2' in event_titles

    event_descriptions = [event['description'] for event in event_list]
    assert 'body1' in event_descriptions
    assert 'body2' in event_descriptions

    event_ids = [event['id'] for event in event_list]

    for e_id in event_ids:
        ev = db.session.query(Event).filter_by(public_id=e_id).one()
        db.session.delete(ev)
    db.session.commit()


def test_api_get(db, api_client, calendar):
    e_data = {'title': 'subj', 'when': {'time': 1},
              'calendar_id': calendar.public_id, 'location': 'InboxHQ'}
    e_data2 = {'title': 'subj2', 'when': {'time': 1},
               'calendar_id': calendar.public_id, 'location': 'InboxHQ'}
    api_client.post_data('/events', e_data)
    api_client.post_data('/events', e_data2)

    event_list = api_client.get_data('/events')

    event_ids = [event['id'] for event in event_list]

    c1found = False
    c2found = False
    for c_id in event_ids:
        event = api_client.get_data('/events/' + c_id)

        if event['title'] == 'subj':
            c1found = True

        if event['title'] == 'subj2':
            c2found = True

    assert c1found
    assert c2found


def test_api_create(db, api_client, calendar, default_account):
    e_data = {
        'title': 'Friday Office Party',
        'calendar_id': calendar.public_id,
        'when': {'time': 1407542195},
        'location': 'Inbox HQ',
    }

    e_resp = api_client.post_data('/events', e_data)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['account_id'] == default_account.namespace.public_id
    assert e_resp_data['title'] == e_data['title']
    assert e_resp_data['location'] == e_data['location']
    assert e_resp_data['when']['time'] == e_data['when']['time']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']
    e_get_resp = api_client.get_data('/events/' + e_id)

    assert e_get_resp['object'] == 'event'
    assert e_get_resp['account_id'] == default_account.namespace.public_id
    assert e_get_resp['id'] == e_id
    assert e_get_resp['title'] == e_data['title']
    assert e_get_resp['when']['time'] == e_data['when']['time']


def test_api_create_no_title(db, api_client, calendar, default_account):
    e_data = {
        'title': '',
        'calendar_id': calendar.public_id,
        'when': {'time': 1407542195},
    }

    e_resp = api_client.post_data('/events', e_data)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['account_id'] == default_account.namespace.public_id
    assert e_resp_data['title'] == e_data['title']
    assert e_resp_data['when']['time'] == e_data['when']['time']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']
    e_get_resp = api_client.get_data('/events/' + e_id)

    assert e_get_resp['object'] == 'event'
    assert e_get_resp['account_id'] == default_account.namespace.public_id
    assert e_get_resp['id'] == e_id
    assert e_get_resp['title'] == e_data['title']
    assert e_get_resp['when']['time'] == e_data['when']['time']


def test_api_update_title(db, api_client, calendar, default_account):
    e_data = {
        'title': '',
        'calendar_id': calendar.public_id,
        'when': {'time': 1407542195},
    }

    e_resp = api_client.post_data('/events', e_data)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['account_id'] == default_account.namespace.public_id
    assert e_resp_data['title'] == e_data['title']
    assert e_resp_data['when']['time'] == e_data['when']['time']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']

    e_update_data = {'title': 'new title'}
    e_put_resp = api_client.put_data('/events/' + e_id, e_update_data)
    e_put_data = json.loads(e_put_resp.data)

    assert e_put_data['object'] == 'event'
    assert e_put_data['account_id'] == default_account.namespace.public_id
    assert e_put_data['id'] == e_id
    assert e_put_data['title'] == 'new title'
    assert e_put_data['when']['object'] == 'time'
    assert e_put_data['when']['time'] == e_data['when']['time']


def test_api_update_invalid(db, api_client, calendar):
    e_update_data = {'title': 'new title'}
    e_id = generate_public_id()
    e_put_resp = api_client.put_data('/events/' + e_id, e_update_data)
    assert e_put_resp.status_code != 200


def test_api_delete(db, api_client, calendar, default_account):
    e_data = {
        'title': '',
        'calendar_id': calendar.public_id,
        'when': {'time': 1407542195},
    }

    e_resp = api_client.post_data('/events', e_data)
    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['title'] == e_data['title']
    assert e_resp_data['when']['time'] == e_data['when']['time']
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']

    e_delete_resp = api_client.delete('/events/' + e_id)
    assert e_delete_resp.status_code == 200

    e_resp = api_client.get_data('/events/' + e_id)
    assert e_resp['status'] == 'cancelled'


def test_api_delete_invalid(db, api_client, calendar):
    e_id = 'asdf'
    resp = api_client.delete('/events/' + e_id)
    assert resp.status_code != 200

    e_id = generate_public_id()
    resp = api_client.delete('/events/' + e_id)
    assert resp.status_code != 200


def test_api_update_read_only(db, api_client, calendar, default_namespace):
    add_fake_event(db.session, default_namespace.id,
                   calendar=calendar,
                   read_only=True)
    event_list = api_client.get_data('/events')

    read_only_event = None
    for e in event_list:
        if e['read_only']:
            read_only_event = e
            break

    assert read_only_event

    e_id = read_only_event['id']
    e_update_data = {'title': 'new title'}
    e_put_resp = api_client.put_data('/events/' + e_id, e_update_data)
    assert e_put_resp.status_code != 200


def test_api_filter(db, api_client, calendar, default_namespace):
    cal = Calendar(namespace_id=default_namespace.id,
                   uid='uid',
                   provider_name='Nylas',
                   name='Climbing Schedule')
    db.session.add(cal)
    db.session.commit()
    cal_id = cal.public_id

    e1_data = {'calendar_id': cal_id,
               'title': 'Normal Party',
               'description': 'Everyone Eats Cake',
               'when': {'time': 1},
               'location': 'Normal Town'}
    post_1 = api_client.post_data('/events', e1_data)
    assert post_1.status_code == 200

    e2_data = {'calendar_id': cal_id,
               'title': 'Hipster Party',
               'description': 'Everyone Eats Kale',
               'when': {'time': 3},
               'location': 'Hipster Town'}
    post_2 = api_client.post_data('/events', e2_data)
    assert post_2.status_code == 200

    # This event exists to test for unicode handling.
    e3_data = {'calendar_id': cal_id,
               'title': u'Unicode Party \U0001F389',
               'description': u'Everyone Eats Unicode Tests \u2713',
               'when': {'start_time': 2678401,
                        'end_time': 5097601},
               'location': u'Unicode Castle \U0001F3F0'}
    event_3 = api_client.post_data('/events', e3_data)
    assert event_3.status_code == 200
    e3_id = json.loads(event_3.data)['id']

    events = api_client.get_data('/events?offset=%s' % '1')
    assert len(events) == 2

    events = api_client.get_data('/events?limit=%s' % '1')
    assert len(events) == 1

    # Test description queries: all, some, unicode, none
    events = api_client.get_data('/events?description=%s' % 'Everyone Eats')
    assert len(events) == 3

    events = api_client.get_data('/events?description=%s' % 'Cake')
    assert len(events) == 1

    events = api_client.get_data('/events?description=%s' % u'\u2713')
    assert len(events) == 1

    events = api_client.get_data('/events?description=%s' % 'bad')
    assert len(events) == 0

    # Test title queries: all, some, unicode, none
    events = api_client.get_data('/events?title=%s' % 'Party')
    assert len(events) == 3

    events = api_client.get_data('/events?title=%s' % 'Hipster')
    assert len(events) == 1

    events = api_client.get_data('/events?title=%s' % u'\U0001F389')
    assert len(events) == 1

    events = api_client.get_data('/events?title=%s' % 'bad')
    assert len(events) == 0

    # Test location queries: all, some, unicode, none
    events = api_client.get_data('/events?location=%s' % 'o')
    assert len(events) == 3

    events = api_client.get_data('/events?location=%s' % 'Town')
    assert len(events) == 2

    events = api_client.get_data('/events?location=%s' % u'\U0001F3F0')
    assert len(events) == 1

    events = api_client.get_data('/events?location=%s' % 'bad')
    assert len(events) == 0

    # Test ID queries
    _filter = 'event_id={}'.format(e3_id)
    events = api_client.get_data('/events?' + _filter)
    assert len(events) == 1

    # Test time queries
    _filter = 'starts_before=2'
    events = api_client.get_data('/events?' + _filter)
    assert len(events) == 1

    _filter = 'starts_after=2'
    events = api_client.get_data('/events?' + _filter)
    assert len(events) == 2

    _filter = 'ends_before=2700000'
    events = api_client.get_data('/events?' + _filter)
    assert len(events) == 2

    _filter = 'ends_after=2700000'
    events = api_client.get_data('/events?' + _filter)
    assert len(events) == 1

    # Test calendar queries
    _filter = 'calendar_id={}'.format(cal_id)
    events = api_client.get_data('/events?' + _filter)
    assert len(events) == 3

    _filter = 'calendar_id=0000000000000000000000000'
    events = api_client.get_data('/events?' + _filter)
    assert len(events) == 0
