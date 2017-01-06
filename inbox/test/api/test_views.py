# flake8: noqa: F811
import pytest
from inbox.test.api.base import api_client, new_api_client
from inbox.test.util.base import generic_account

__all__ = ['api_client', 'generic_account']


# Label views should only work for Gmail accounts. folders 404
@pytest.mark.parametrize('resource_name',
                         ['messages', 'drafts', 'files', 'events',
                          'folders', 'labels', 'calendars', 'contacts'])
def test_resource_views(resource_name, db, api_client, generic_account,
                        message, thread, event, label, contact, folder):
    """Exercises various tests for views, mostly related to
    filtering. Note: this only tests views, it assumes the
    resources are working as expected."""
    # Folders don't work with GMail accounts, need generic IMAP
    if resource_name == 'folders':
        api_client = new_api_client(db, generic_account.namespace)
    elements = api_client.get_data('/{}'.format(resource_name))
    count = api_client.get_data('/{}?view=count'.format(resource_name))

    assert count["count"] == len(elements)

    ids = api_client.get_data('/{}?view=ids'.format(resource_name))

    for i, elem in enumerate(elements):
        assert isinstance(ids[i], basestring), \
            "&views=ids should return string"
        assert elem["id"] == ids[i], "view=ids should preserve order"
