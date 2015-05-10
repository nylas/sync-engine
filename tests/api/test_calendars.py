from inbox.models import Calendar
from tests.util.base import api_client, default_account

__all__ = ['api_client']


def test_api_list(db, default_account, api_client):
    calendar_list = api_client.get_data('/calendars')

    cal = None
    for c in calendar_list:
        if c['name'] == 'default':
            cal = c
    assert cal
    assert cal['object'] == 'calendar'
    assert cal['name'] == 'default'
    assert cal['read_only'] is False
    assert cal['namespace_id'] == default_account.namespace.public_id


def test_get_calendar(db, default_account, api_client):
    cal = Calendar(
        namespace_id=default_account.namespace.id,
        uid='uid',
        provider_name='WTF',
        name='Holidays')
    db.session.add(cal)
    db.session.commit()
    cal_id = cal.public_id

    resp_data = api_client.get_data('/calendars/' + cal_id)
    assert resp_data['namespace_id'] == default_account.namespace.public_id
    assert resp_data['name'] == 'Holidays'
    assert resp_data['description'] is None
    assert resp_data['read_only'] is False
    assert resp_data['object'] == 'calendar'


def test_handle_not_found_calendar(api_client):
    resp_data = api_client.get_raw('/calendars/foo')
    assert resp_data.status_code == 404


def test_add_to_specific_calendar(db, default_account, api_client):
    cal = Calendar(
        namespace_id=default_account.namespace.id,
        uid='uid',
        provider_name='WTF',
        name='Custom')
    db.session.add(cal)
    db.session.commit()
    cal_id = cal.public_id

    e_data = {'calendar_id': cal_id,
              'title': 'subj', 'description': 'body1',
              'when': {'time': 1}, 'location': 'InboxHQ'}
    r = api_client.post_data('/events', e_data)
    assert r.status_code == 200

    events = api_client.get_data('/events?calendar_id={}'.format(cal_id))
    assert len(events) == 1


def test_add_to_read_only_calendar(db, api_client):
    cal_list = api_client.get_data('/calendars')
    assert len(cal_list) == 2
    ro_cal = None
    for c in cal_list:
        if c['read_only']:
            ro_cal = c

    assert ro_cal

    e_data = {'calendar_id': ro_cal['id'],
              'title': 'subj', 'description': 'body1',
              'when': {'time': 1}, 'location': 'InboxHQ'}
    resp = api_client.post_data('/events', e_data)
    assert resp.status_code == 400


def test_delete_from_readonly_calendar(db, api_client):
    calendar_list = api_client.get_data('/calendars')

    read_only_calendar = None
    for c in calendar_list:
        if c['read_only']:
            read_only_calendar = c
            break
    events = api_client.get_data('/events?calendar_id={}'.format(
        read_only_calendar['id']))
    for event in events:
        if event['read_only']:
            read_only_event = event
            break

    assert read_only_calendar
    assert read_only_event
    e_id = read_only_event['id']
    resp = api_client.delete('/events/{}'.format(e_id))
    assert resp.status_code == 400
