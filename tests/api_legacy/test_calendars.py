from tests.util.base import add_fake_event
from inbox.models import Calendar
from tests.api_legacy.base import api_client
from tests.util.base import db, default_namespace


__all__ = ['api_client', 'db', 'default_namespace']


def test_get_calendar(db, default_namespace, api_client):
    cal = Calendar(
        namespace_id=default_namespace.id,
        uid='uid',
        provider_name='WTF',
        name='Holidays')
    db.session.add(cal)
    db.session.commit()
    cal_id = cal.public_id
    calendar_item = api_client.get_data('/calendars/{}'.format(cal_id))

    assert calendar_item['namespace_id'] == default_namespace.public_id
    assert calendar_item['name'] == 'Holidays'
    assert calendar_item['description'] is None
    assert calendar_item['read_only'] is False
    assert calendar_item['object'] == 'calendar'


def test_handle_not_found_calendar(api_client):
    resp_data = api_client.get_raw('/calendars/foo')
    assert resp_data.status_code == 404


def test_add_to_specific_calendar(db, default_namespace, api_client):
    cal = Calendar(
        namespace_id=default_namespace.id,
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


def test_delete_from_readonly_calendar(db, default_namespace, api_client):

    add_fake_event(db.session, default_namespace.id,
                   calendar=db.session.query(Calendar).filter(
                       Calendar.namespace_id == default_namespace.id,
                       Calendar.read_only == True).first(),  # noqa
                   read_only=True)
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
