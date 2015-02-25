import pytest
from mockredis import mock_strict_redis_client

from inbox.heartbeat.store import HeartbeatStore


def mock_client():
    mock_client = mock_strict_redis_client()

    # Adding a couple of methods we use that mockredis doesn't support yet.
    def scan_iter_patch(match=None, count=100):
        match = str(match).replace('*', '')
        return filter(lambda k: k.startswith(match), mock_client.keys())

    mock_client.scan_iter = scan_iter_patch
    mock_client.reset = lambda: True

    def zscan_iter_patch(key, match=None):
        match = str(match).replace('*', '')
        return filter(lambda k: k.startswith(match),
                      mock_client.zrange(key, 0, -1))
    mock_client.zscan_iter = zscan_iter_patch
    return mock_client


@pytest.yield_fixture()
def redis_client(monkeypatch):
    client = mock_client()
    yield client
    # Flush on teardown
    client.flushdb()


@pytest.fixture(scope='function', autouse=True)
def redis_mock(redis_client, monkeypatch):
    def set_self_client(self, *args, **kwargs):
        # Ensure the same 'redis' client is returned across HeartbeatStore
        # calls and direct checks. Mocking StrictRedis() directly causes
        # different clients to be initialized, so we can't check contents.
        self.client = redis_client

    monkeypatch.setattr("inbox.heartbeat.store.HeartbeatStore.__init__",
                        set_self_client)


@pytest.fixture(scope='function', autouse=True)
def store(monkeypatch):
    local_store = HeartbeatStore()

    @classmethod
    def scoped_store(*args, **kwargs):
        return local_store

    # Circumvent singleton behaviour for tests
    monkeypatch.setattr("inbox.heartbeat.store.HeartbeatStore.store",
                        scoped_store)

    return HeartbeatStore.store()
