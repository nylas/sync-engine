import pytest
from tests.util.base import api_client, test_client


def generic_test_resource(resource_name, db, client):
    """Exercises various tests for views, mostly related to
    filtering. Note: this only tests views, it assumes the
    resources are working as expected."""
    elements = client.get_data('/{}'.format(resource_name))
    count = client.get_data('/{}?view=count'.format(resource_name))

    assert count["count"] == len(elements)

    ids = client.get_data('/{}?view=ids'.format(resource_name))

    for i, elem in enumerate(elements):
        assert isinstance(ids[i], basestring), "&views=ids should return string"
        assert elem["id"] == ids[i], "view=ids should preserve order"


def test_tags(db, api_client):
    generic_test_resource("tags", db, api_client)


def test_messages(db, api_client):
    generic_test_resource("messages", db, api_client)


def test_drafts(db, api_client):
    generic_test_resource("drafts", db, api_client)


def test_files(db, api_client):
    generic_test_resource("files", db, api_client)


def test_events(db, api_client):
    generic_test_resource("events", db, api_client)


if __name__ == '__main__':
    pytest.main([__file__])
