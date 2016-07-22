# flake8: noqa: F401
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


@pytest.yield_fixture(scope='function')
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
        self.host = None
        self.port = 6379

    def fake_redis_client(host=None, port=6379, db=1):
        return redis_client

    monkeypatch.setattr("inbox.heartbeat.config.get_redis_client",
                        fake_redis_client)
    monkeypatch.setattr("inbox.heartbeat.store.HeartbeatStore.__init__",
                        set_self_client)
