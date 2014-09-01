import json
import pytest

from inbox.models import Account
from tests.util.base import api_client
__all__ = ['api_client']

ACCOUNT_ID = 1


class CreateError(Exception):
    pass


def _verify_create(ns_id, api_client, e_data):
    e_resp = api_client.post_data('/events', e_data, ns_id)
    if e_resp.status_code != 200:
        raise CreateError()

    e_resp_data = json.loads(e_resp.data)
    assert e_resp_data['object'] == 'event'
    assert e_resp_data['namespace_id'] == ns_id
    assert e_resp_data['title'] == e_data['title']
    assert e_resp_data['location'] == e_data['location']
    for k, v in e_data['when'].iteritems():
        assert e_resp_data['when'][k] == v
    assert 'id' in e_resp_data
    e_id = e_resp_data['id']
    e_get_resp = api_client.get_data('/events/' + e_id, ns_id)

    assert e_get_resp['object'] == 'event'
    assert e_get_resp['namespace_id'] == ns_id
    assert e_get_resp['id'] == e_id
    assert e_get_resp['title'] == e_data['title']
    for k, v in e_data['when'].iteritems():
        assert e_get_resp['when'][k] == v

    return e_resp_data


def test_api_time(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'title': 'Friday Office Party',
        'when': {'time': 1407542195},
        'location': 'Inbox HQ',
    }

    e_resp_data = _verify_create(ns_id, api_client, e_data)
    assert e_resp_data['when']['object'] == 'time'


def test_api_timespan(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'title': 'Friday Office Party',
        'when': {'start_time': 1407542195, 'end_time': 1407548195},
        'location': 'Inbox HQ',
    }

    e_resp_data = _verify_create(ns_id, api_client, e_data)
    assert e_resp_data['when']['object'] == 'timespan'


def test_api_date(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'title': 'Friday Office Party',
        'when': {'date': '2014-08-27'},
        'location': 'Inbox HQ',
    }

    e_resp_data = _verify_create(ns_id, api_client, e_data)
    assert e_resp_data['when']['object'] == 'date'


def test_api_datespan(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {
        'title': 'Friday Office Party',
        'when': {'start_date': '2014-08-27', 'end_date': '2014-08-28'},
        'location': 'Inbox HQ',
    }

    e_resp_data = _verify_create(ns_id, api_client, e_data)
    assert e_resp_data['when']['object'] == 'datespan'


# Invalid


def test_api_invalid_event_no_when(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {'title': 'Friday Office Party'}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)


def test_api_invalid_event_when_no_params(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {'title': 'Friday Office Party', 'when': {}}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)


def test_api_invalid_event_when_bad_params(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    e_data = {'title': 'Friday Office Party', 'when': {'start': 0}}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)


def test_api_invalid_event_when_timespan_bad_params(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    e_data = {'title': 'Friday Office Party'}

    e_data['when'] = {'object': 'time', 'start': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'object': 'time', 'start_time': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_time': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_time': 'a', 'end_time': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_time': 0, 'end_time': 'a'}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_time': 0, 'end_time': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_time': 0, 'end_time': 1, 'time': 2}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)


def test_api_invalid_event_when_datespan_bad_params(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    e_data = {'title': 'Friday Office Party'}

    e_data['when'] = {'object': 'date', 'start': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'object': 'date', 'start_date': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_date': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_date': 'a', 'end_date': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_date': 0, 'end_date': 'a'}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_date': '2014-08-27',
                      'end_date': '2014-08-27'}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'start_date': '2014-08-27',
                      'end_date': '2014-08-28',
                      'date': '2014-08-27'}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)


def test_api_invalid_event_when_time_bad_params(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    e_data = {'title': 'Friday Office Party'}

    e_data['when'] = {'object': 'date', 'time': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'time': 'a'}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'time': 0, 'date': '2014-08-23'}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)


def test_api_invalid_event_when_date_bad_params(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    e_data = {'title': 'Friday Office Party'}

    e_data['when'] = {'object': 'time', 'date': 0}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)

    e_data['when'] = {'date': 'j'}
    with pytest.raises(CreateError):
        _verify_create(ns_id, api_client, e_data)


def test_api_event_when_update(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    e_data = {'title': 'Friday Office Party', 'location': 'home'}
    e_data['when'] = {'time': 0}
    e_resp_data = _verify_create(ns_id, api_client, e_data)
    e_id = e_resp_data['id']

    e_update_data = {'when': {'time': 1}}
    e_put_resp = api_client.put_data('/events/' + e_id, e_update_data, ns_id)
    e_put_data = json.loads(e_put_resp.data)
    assert e_put_data['when']['object'] == 'time'
    assert e_put_data['when']['time'] == e_update_data['when']['time']
