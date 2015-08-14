import json
from pytest import yield_fixture


def new_api_client(db, namespace):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        return TestAPIClient(c, namespace.public_id)


@yield_fixture
def api_client(db, default_namespace):
    from inbox.api.srv import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield TestAPIClient(c, default_namespace.public_id)


class TestAPIClient(object):
    """Provide more convenient access to the API for testing purposes."""
    def __init__(self, test_client, default_ns_public_id):
        self.client = test_client
        self.default_ns_public_id = default_ns_public_id

    def full_path(self, path, ns_public_id=None):
        """ Replace a path such as `/tags` by `/n/<ns_public_id>/tags`.

        If no `ns_public_id` is specified, uses the id of the first namespace
        returned by a call to `/n/`.
        """
        if ns_public_id is None:
            ns_public_id = self.default_ns_public_id

        return '/n/{}'.format(ns_public_id) + path

    def get_raw(self, short_path, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return self.client.get(path)

    def get_data(self, short_path, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return json.loads(self.client.get(path).data)

    def post_data(self, short_path, data, ns_public_id=None, headers=''):
        path = self.full_path(short_path, ns_public_id)
        return self.client.post(path, data=json.dumps(data), headers=headers)

    def post_raw(self, short_path, data, ns_public_id=None, headers=''):
        path = self.full_path(short_path, ns_public_id)
        return self.client.post(path, data=data, headers=headers)

    def put_data(self, short_path, data, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return self.client.put(path, data=json.dumps(data))

    def delete(self, short_path, data=None, ns_public_id=None):
        path = self.full_path(short_path, ns_public_id)
        return self.client.delete(path, data=json.dumps(data))
