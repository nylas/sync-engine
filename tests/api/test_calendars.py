import json

from inbox.models import Account, Calendar
from tests.util.base import api_client

__all__ = ['api_client']


ACCOUNT_ID = 1


def test_api_list(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    calendar_list = api_client.get_data('/calendars', ns_id)

    cal = None
    for c in calendar_list:
        if c['name'] == 'default':
            cal = c
    assert cal
    assert cal['object'] == 'calendar'
    assert cal['name'] == 'default'
    assert cal['read_only'] is False
    assert cal['namespace'] == ns_id


def test_create_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {'name': 'Birthdays'}

    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)
    cal_id = resp_data['id']

    assert resp_data['namespace'] == ns_id
    assert resp_data['name'] == c_data['name']
    assert resp_data['description'] is None
    assert resp_data['read_only'] is False
    assert resp_data['object'] == 'calendar'
    assert resp_data['event_ids'] == []

    cal = db.session.query(Calendar).filter_by(public_id=cal_id).one()
    db.session.delete(cal)
    db.session.commit()


def test_create_calendar_conflict(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {'name': 'Birthdays'}

    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)
    cal_id = resp_data['id']

    resp = api_client.post_data('/calendars', c_data, ns_id)
    assert resp.status_code != 200

    cal = db.session.query(Calendar).filter_by(public_id=cal_id).one()
    db.session.delete(cal)
    db.session.commit()


def test_get_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {'name': 'Holidays'}

    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)
    cal_id = resp_data['id']

    resp_data = api_client.get_data('/calendars/' + cal_id, ns_id)
    assert resp_data['namespace'] == ns_id
    assert resp_data['name'] == c_data['name']
    assert resp_data['description'] is None
    assert resp_data['read_only'] is False
    assert resp_data['object'] == 'calendar'
    assert resp_data['event_ids'] == []

    cal = db.session.query(Calendar).filter_by(public_id=cal_id).one()
    db.session.delete(cal)
    db.session.commit()


def test_filter_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {'name': 'Holidays', 'description': 'Local Holidays'}

    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)
    cal_id = resp_data['id']

    _filter = "?filter=Holidays"

    resp_data = api_client.get_data('/calendars' + _filter, ns_id)[0]
    assert resp_data['namespace'] == ns_id
    assert resp_data['name'] == c_data['name']
    assert resp_data['description'] == 'Local Holidays'
    assert resp_data['read_only'] is False
    assert resp_data['object'] == 'calendar'
    assert resp_data['event_ids'] == []

    _filter = "?filter=Local%20Holidays"
    resp_data = api_client.get_data('/calendars' + _filter, ns_id)
    assert len(resp_data) == 1

    cal = db.session.query(Calendar).filter_by(public_id=cal_id).one()
    db.session.delete(cal)
    db.session.commit()


def test_update_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {'name': 'Vacation'}

    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)

    cal_id = resp_data['id']

    c_update_data = {'name': 'OOO'}
    resp = api_client.put_data('/calendars/' + cal_id, c_update_data, ns_id)
    c_put_data = json.loads(resp.data)
    assert resp.status_code == 200
    assert c_put_data['namespace'] == ns_id
    assert c_put_data['name'] == c_update_data['name']
    assert c_put_data['description'] is None
    assert c_put_data['read_only'] is False
    assert c_put_data['object'] == 'calendar'
    assert c_put_data['event_ids'] == []

    resp_data = api_client.get_data('/calendars/' + cal_id, ns_id)
    assert resp_data['namespace'] == ns_id
    assert resp_data['name'] == c_update_data['name']
    assert resp_data['description'] is None
    assert resp_data['read_only'] is False
    assert resp_data['object'] == 'calendar'
    assert resp_data['event_ids'] == []

    cal = db.session.query(Calendar).filter_by(public_id=cal_id).one()
    db.session.delete(cal)
    db.session.commit()


def test_delete_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {'name': 'Work'}

    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)

    cal_id = resp_data['id']

    resp = api_client.delete('/calendars/' + cal_id, ns_id)
    assert resp.status_code == 200

    event = api_client.get_data('/calendars/' + cal_id, ns_id)
    assert event['type'] == 'invalid_request_error'


def test_add_to_default_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    default_calendar = acct.default_calendar
    ns_id = acct.namespace.public_id
    old_length = len(default_calendar.events)

    e_data = {'title': 'subj', 'description': 'body1',
              'when': {'time': 1}, 'location': 'InboxHQ'}
    api_client.post_data('/events', e_data, ns_id)

    cal_list = api_client.get_data('/calendars', ns_id)
    event_list = cal_list[0]['event_ids']

    assert len(event_list) == old_length + 1


def test_add_to_specific_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {'name': 'Custom'}
    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)
    cal_id = resp_data['id']

    e_data = {'calendar_id': cal_id,
              'title': 'subj', 'description': 'body1',
              'when': {'time': 1}, 'location': 'InboxHQ'}
    api_client.post_data('/events', e_data, ns_id)

    _filter = "?filter=Custom"
    cal_list = api_client.get_data('/calendars' + _filter, ns_id)
    event_list = cal_list[0]['event_ids']

    assert len(event_list) == 1

    cal = db.session.query(Calendar).filter_by(public_id=cal_id).one()
    db.session.delete(cal)
    db.session.commit()


def test_add_to_read_only_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    cal_list = api_client.get_data('/calendars', ns_id)
    assert len(cal_list) == 2
    ro_cal = None
    for c in cal_list:
        if c['read_only']:
            ro_cal = c

    assert ro_cal

    e_data = {'calendar_id': ro_cal['id'],
              'title': 'subj', 'description': 'body1',
              'when': {'time': 1}, 'location': 'InboxHQ'}
    resp = api_client.post_data('/events', e_data, ns_id)
    assert resp.status_code != 200


def test_delete_calendar_deletes_events(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {'name': 'TBD'}
    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)
    cal_id = resp_data['id']

    e_data = {'calendar_id': cal_id,
              'title': 'subj', 'description': 'body1',
              'when': {'time': 1}, 'location': 'InboxHQ'}
    api_client.post_data('/events', e_data, ns_id)
    _filter = "?filter=TBD"
    cal_list = api_client.get_data('/calendars' + _filter, ns_id)
    event_id = cal_list[0]['event_ids'][0]

    resp = api_client.get_data('/events/' + event_id, ns_id)

    resp = api_client.delete('/calendars/' + cal_id, ns_id)
    assert resp.status_code == 200

    resp = api_client.get_data('/events/' + event_id, ns_id)
    assert resp['type'] == 'invalid_request_error'


def test_delete_from_readonly_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    calendar_list = api_client.get_data('/calendars', ns_id)

    read_only_calendar = None
    for c in calendar_list:
        if c['read_only']:
            read_only_calendar = c
            for e_id in c['event_ids']:
                e = api_client.get_data('/events/' + e_id, ns_id)
                if e['read_only']:
                    read_only_event = e
                    break

    assert read_only_calendar
    assert read_only_event
    e_id = read_only_event['id']
    resp = api_client.delete('/events/' + e_id, ns_id=ns_id)
    assert resp.status_code != 200


def test_move_to_read_only_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    calendar_list = api_client.get_data('/calendars', ns_id)

    read_only_calendar = None
    writeable_calendar = None
    writeable_event = None
    for c in calendar_list:
        if c['read_only']:
            read_only_calendar = c
        else:
            writeable_calendar = c
            for e_id in c['event_ids']:
                e = api_client.get_data('/events/' + e_id, ns_id)
                if not e['read_only']:
                    writeable_event = e
                    break

    assert read_only_calendar
    assert writeable_event
    assert writeable_calendar
    e_id = writeable_event['id']

    e_data = {'calendar_id': read_only_calendar['id']}
    resp = api_client.put_data('/events/' + e_id, e_data, ns_id)
    assert resp.status_code != 200


def test_move_event(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    calendar_list = api_client.get_data('/calendars', ns_id)

    writeable_calendar = None
    writeable_event = None
    for c in calendar_list:
        if not c['read_only']:
            writeable_calendar = c
            for e_id in c['event_ids']:
                e = api_client.get_data('/events/' + e_id, ns_id)
                if not e['read_only']:
                    writeable_event = e
                    break

    assert writeable_event
    assert writeable_calendar
    e_id = writeable_event['id']

    c_data = {'name': 'Birthdays'}
    resp = api_client.post_data('/calendars', c_data, ns_id)
    resp_data = json.loads(resp.data)
    cal_id = resp_data['id']

    e_data = {'calendar_id': cal_id}
    resp = api_client.put_data('/events/' + e_id, e_data, ns_id)
    assert resp.status_code == 200

    event = api_client.get_data('/events/' + e_id, ns_id)
    assert event['calendar_id'] == cal_id

    e_data = {'calendar_id': writeable_calendar['id']}
    resp = api_client.put_data('/events/' + e_id, e_data, ns_id)
    assert resp.status_code == 200

    event = api_client.get_data('/events/' + e_id, ns_id)
    assert event['calendar_id'] == writeable_calendar['id']

    cal = db.session.query(Calendar).filter_by(public_id=cal_id).one()
    db.session.delete(cal)
    db.session.commit()


def test_update_readonly_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    calendar_list = api_client.get_data('/calendars', ns_id)

    read_only_calendar = None
    for c in calendar_list:
        if c['read_only']:
            read_only_calendar = c

    assert read_only_calendar
    cal_id = read_only_calendar['id']

    c_update_data = {'name': 'SHOULD_NOT_SUCCEED'}
    resp = api_client.put_data('/calendars/' + cal_id, c_update_data, ns_id)
    assert resp.status_code == 400


def test_delete_readonly_calendar(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    calendar_list = api_client.get_data('/calendars', ns_id)

    read_only_calendar = None
    for c in calendar_list:
        if c['read_only']:
            read_only_calendar = c

    assert read_only_calendar
    cal_id = read_only_calendar['id']

    resp = api_client.delete('/calendars/' + cal_id, ns_id)
    assert resp.status_code == 400
