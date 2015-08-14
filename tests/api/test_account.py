from tests.util.base import generic_account, gmail_account, db
from tests.api.base import api_client, new_api_client

__all__ = ['db', 'api_client', 'generic_account', 'gmail_account']


def test_account(db, api_client, generic_account, gmail_account):

    # Because we're using the generic_account namespace
    api_client = new_api_client(db, generic_account.namespace)

    resp_data = api_client.get_data('/account')

    assert resp_data['id'] == generic_account.namespace.public_id
    assert resp_data['object'] == 'account'
    assert resp_data['account_id'] == generic_account.namespace.public_id
    assert resp_data['email_address'] == generic_account.email_address
    assert resp_data['name'] == generic_account.name
    assert resp_data['organization_unit'] == 'folder'

    # Because we're using the gmail account namespace
    api_client = new_api_client(db, gmail_account.namespace)

    resp_data = api_client.get_data('/account')

    assert resp_data['id'] == gmail_account.namespace.public_id
    assert resp_data['provider'] == 'gmail'
    assert resp_data['organization_unit'] == 'label'
