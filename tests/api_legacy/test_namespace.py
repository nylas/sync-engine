from tests.util.base import generic_account, gmail_account
from tests.api_legacy.base import api_client

__all__ = ['api_client', 'generic_account', 'gmail_account']


def test_namespace(api_client, generic_account, gmail_account):
    resp_data = api_client.get_data('', generic_account.namespace.public_id)

    assert resp_data['id'] == generic_account.namespace.public_id
    assert resp_data['object'] == 'namespace'
    assert resp_data['namespace_id'] == generic_account.namespace.public_id
    assert resp_data['account_id'] == generic_account.public_id
    assert resp_data['email_address'] == generic_account.email_address
    assert resp_data['name'] == generic_account.name
    assert resp_data['organization_unit'] == 'folder'

    resp_data = api_client.get_data('', gmail_account.namespace.public_id)

    assert resp_data['id'] == gmail_account.namespace.public_id
    assert resp_data['provider'] == 'gmail'
    assert resp_data['organization_unit'] == 'label'
