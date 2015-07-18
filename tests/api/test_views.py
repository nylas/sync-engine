import pytest


@pytest.mark.parametrize('resource_name',
                         ['messages', 'drafts', 'files', 'events', 'labels',
                          'folders', 'calendars', 'contacts'])
def test_resource_views(resource_name, db, api_client,
                        message, thread, event, folder, label, contact):
    """Exercises various tests for views, mostly related to
    filtering. Note: this only tests views, it assumes the
    resources are working as expected."""
    elements = api_client.get_data('/{}'.format(resource_name))
    count = api_client.get_data('/{}?view=count'.format(resource_name))

    assert count["count"] == len(elements)

    ids = api_client.get_data('/{}?view=ids'.format(resource_name))

    for i, elem in enumerate(elements):
        assert isinstance(ids[i], basestring), "&views=ids should return string"
        assert elem["id"] == ids[i], "view=ids should preserve order"
