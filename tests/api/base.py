import json
from pytest import fixture, yield_fixture
from base64 import b64encode


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


@fixture
def imap_api_client(db, generic_account):
    return new_api_client(db, generic_account.namespace)


class TestAPIClient(object):

    """Provide more convenient access to the API for testing purposes."""

    def __init__(self, test_client, default_namespace_public_id):
        self.client = test_client
        credential = '{}:'.format(default_namespace_public_id)
        self.auth_header = {'Authorization': 'Basic {}'
                            .format(b64encode(credential))}

    def get_raw(self, path, headers={}):
        headers.update(self.auth_header)
        return self.client.get(path, headers=headers)

    def get_data(self, path):
        return json.loads(self.client.get(path, headers=self.auth_header).data)

    def post_data(self, path, data, headers={}):
        headers.update(self.auth_header)
        return self.client.post(path, data=json.dumps(data), headers=headers)

    def post_raw(self, path, data, headers={}):
        headers.update(self.auth_header)
        return self.client.post(path, data=data, headers=headers)

    def put_data(self, path, data):
        return self.client.put(path, headers=self.auth_header,
                               data=json.dumps(data))

    def delete(self, path, data=None):
        return self.client.delete(path, headers=self.auth_header,
                                  data=json.dumps(data))
