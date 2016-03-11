import json
from base64 import b64encode


from tests.util.base import generic_account, db  # noqa
from tests.api.base import new_api_client  # noqa


def test_no_auth(db, generic_account):  # noqa
    # Because we're using the generic_account namespace

    api_client = new_api_client(db, generic_account.namespace)
    api_client.auth_header = {}

    response = api_client.get_raw('/account')
    assert response.status_code == 401


def test_basic_auth(db, generic_account):  # noqa
    api_client = new_api_client(db, generic_account.namespace)

    response = api_client.get_raw('/account')
    assert response.status_code == 200

    resp_data = json.loads(response.data)
    assert resp_data['id'] == generic_account.namespace.public_id


def test_bearer_token_auth(db, generic_account):  # noqa
    api_client = new_api_client(db, generic_account.namespace)
    api_client.auth_header = {
        'Authorization': 'Bearer {}'
        .format(generic_account.namespace.public_id)}

    response = api_client.get_raw('/account')
    assert response.status_code == 200

    resp_data = json.loads(response.data)
    assert resp_data['id'] == generic_account.namespace.public_id


BAD_TOKEN = '1234567890abcdefg'


def test_invalid_basic_auth(db, generic_account):  # noqa
    api_client = new_api_client(db, generic_account.namespace)
    api_client.auth_header = {'Authorization': 'Basic {}'
                              .format(b64encode(BAD_TOKEN + ':'))}

    response = api_client.get_raw('/account')
    assert response.status_code == 401


def test_invalid_bearer_token_auth(db, generic_account):  # noqa
    api_client = new_api_client(db, generic_account.namespace)
    api_client.auth_header = {
        'Authorization': 'Bearer {}'.format(BAD_TOKEN)}

    response = api_client.get_raw('/account')
    assert response.status_code == 401
