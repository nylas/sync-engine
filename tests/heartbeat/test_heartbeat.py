import pytest
import json
import time
from datetime import datetime, timedelta

from inbox.heartbeat.store import (HeartbeatStore, HeartbeatStatusProxy,
                                   HeartbeatStatusKey)
from inbox.heartbeat.status import (clear_heartbeat_status, list_all_accounts,
                                    list_alive_accounts, list_dead_accounts,
                                    heartbeat_summary, get_account_metadata,
                                    get_heartbeat_status,
                                    AccountHeartbeatStatus)
from inbox.heartbeat.config import ALIVE_EXPIRY

from inbox.log import configure_logging
configure_logging()

from mockredis import MockRedis
# Note that all Redis commands are mocked via mockredis in conftest.py.


def proxy_for(account_id, folder_id, email='test@test.com', provider='gmail',
              device_id=0):
    return HeartbeatStatusProxy(account_id=account_id, folder_id=folder_id,
                                folder_name="Inbox",
                                email_address=email,
                                provider_name=provider,
                                device_id=device_id)


def fuzzy_equals(a, b):
    if isinstance(a, datetime) or isinstance(b, datetime):
        if not isinstance(a, datetime):
            b = datetime.fromtimestamp(a)
        if not isinstance(b, datetime):
            b = datetime.fromtimestamp(b)
        s = abs(a - b)
        return s < timedelta(seconds=0.1)
    return abs(a - b) < 0.1


# Test storing and removing heartbeats


def test_heartbeat_store_singleton():
    # Test we don't unnecessarily create multiple instances of HeartbeatStore
    store_one = HeartbeatStore.store()
    store_two = HeartbeatStore.store()
    assert isinstance(store_one.client, MockRedis)
    assert id(store_one) == id(store_two)


def test_heartbeat_status_key():
    account_id = 1
    folder_id = 2
    key = HeartbeatStatusKey(account_id, folder_id)
    assert str(key) == "1:2"
    key = HeartbeatStatusKey.from_string("2:1")
    assert key.account_id == 2
    assert key.folder_id == 1


def test_proxy_publishes_on_init(redis_client):
    proxy = proxy_for(1, 2)
    # Check there was an initial publish
    assert "1:2" in redis_client.keys()
    folder = redis_client.hgetall("1:2")
    # Check Gmail account published to device '0'
    assert folder.keys() == ['0']
    # Check the published keys were valid
    folder = json.loads(folder['0'])
    assert all([k in proxy.schema for k in folder.keys()])
    assert 'folder_name' in folder.keys()
    assert 'email_address' in folder.keys()
    assert 'provider_name' in folder.keys()


def test_proxy_publish_doesnt_break_everything(monkeypatch):
    def break_things(s, k, d, v):
        raise Exception("Redis connection failure")
    monkeypatch.setattr("mockredis.MockRedis.hset", break_things)
    # Check heartbeat publish exception doesn't pass up through to caller.
    # It will print out an error in the log, though.
    proxy_for(1, 2)
    assert True


def test_folder_publish_in_index(redis_client):
    proxy = proxy_for(1, 2)
    assert 'folder_index' in redis_client.keys()
    assert 'account_index' in redis_client.keys()
    assert '1' in redis_client.keys()
    assert '1:2' in redis_client.keys()

    # Check the folder index was populated correctly: it should be a sorted
    # set of all folder keys with the timestamp of the last heartbeat
    folder_index = redis_client.zrange('folder_index', 0, -1, withscores=True)
    assert len(folder_index) == 1
    key, timestamp = folder_index[0]
    assert key == '1:2'
    assert fuzzy_equals(proxy.heartbeat_at, timestamp)

    # Check the account index was populated correctly: it should be a sorted
    # set of all account IDs with the timestamp of the oldest heartbeat
    acct_index = redis_client.zrange('account_index', 0, -1, withscores=True)
    assert len(acct_index) == 1
    key, timestamp = acct_index[0]
    assert key == '1'
    assert fuzzy_equals(proxy.heartbeat_at, timestamp)

    # Check the per-account folder-list index was populated correctly: it
    # should be a sorted set of all folder IDs for that account, with the
    # folder's last heartbeat timestamp.
    acct_folder_index = redis_client.zrange('1', 0, -1, withscores=True)
    assert len(acct_folder_index) == 1
    key, timestamp = acct_folder_index[0]
    assert key == '2'
    assert fuzzy_equals(proxy.heartbeat_at, timestamp)


def test_account_index_oldest_timestamp(redis_client):
    # Test that when we publish heartbeats to two different folders for an
    # account, the account's timestamp in the index is the oldest of the two.
    proxies = []
    for i in [2, 3]:
        proxies.append(proxy_for(1, i))
        time.sleep(0.5)

    # Check that folder 3 is in the right place
    acct_folder_index = redis_client.zrange('1', 0, -1, withscores=True)
    assert len(acct_folder_index) == 2
    # The highest score should belong to folder 3.
    acct_folder_index = redis_client.zrevrange('1', 0, 0)
    assert acct_folder_index[0] == '3'

    # Check the timestamp on the account itself.
    acct_index = redis_client.zrange('account_index', 0, -1, withscores=True)
    assert len(acct_index) == 1
    key, timestamp = acct_index[0]
    # The proxy heartbeat_at is the time it was published by the proxy, whereas
    # the index time is the time the index was updated, so they may differ but
    # only by a very small amount.
    assert fuzzy_equals(proxies[0].heartbeat_at, timestamp)


def test_remove_folder_from_index(redis_client, store):
    # When we remove a folder, it should also be removed from the folder
    # index and the account's timestamp updated accordingly.
    proxies = []
    for i in [2, 3]:
        proxies.append(proxy_for(1, i))
        time.sleep(0.5)

    n = store.remove_folders(1, 2)
    assert n == 1
    # Folder is removed
    assert redis_client.hgetall("1:2") == {}
    # Folder index is removed
    folder_ids = [f for f, ts in store.get_folder_list()]
    assert folder_ids == ['1:3']
    # Account-folder index is removed
    account_folders = [f for f, ts in store.get_account_folders(1)]
    assert account_folders == ['3']
    # Account timestamp is updated
    account_timestamp = store.get_account_timestamp(1)
    assert fuzzy_equals(proxies[1].heartbeat_at, account_timestamp)


def test_remove_account_from_index(store):
    for i in [2, 3]:
        proxy_for(1, i)
    n = clear_heartbeat_status(1)
    assert n == 2
    assert store.get_folder_list() == []


def test_publish_with_timestamp(store):
    # Test that if we publish with an explicit timestamp argument, the
    # heartbeat has that timestamp, not now.
    proxy = proxy_for(1, 2)
    timestamp = datetime(2015, 01, 01, 02, 02, 02)
    proxy.publish(heartbeat_at=timestamp)
    account_timestamp = store.get_account_timestamp(1)
    assert account_timestamp == time.mktime(timestamp.timetuple())


def test_kill_device_multiple(store):
    # If we kill a device and the folder has multiple devices, don't clear
    # the heartbeat status
    proxy_for(1, 2, device_id=2)
    proxy_for(1, 2, device_id=3)
    clear_heartbeat_status(1, device_id=2)
    folders = store.get_account_folders(1)
    (f, ts) = folders[0]
    assert f == '2'


def test_kill_device_lastone(store):
    # If we kill a device and it's the only device publishing heartbeats for
    # that folder, the folder is removed when the device is removed.
    proxy_for(1, 2, device_id=2)
    clear_heartbeat_status(1, device_id=2)
    folders = store.get_account_folders(1)
    assert len(folders) == 0


# Test querying heartbeats


@pytest.fixture
def random_heartbeats():
    # generate some random heartbeats for accounts 1..10 and folders -2..2
    proxies = {}
    for i in range(10):
        proxies[i] = {}
        for f in range(-2, 3):
            proxies[i][f] = proxy_for(i, f)
    return proxies


def make_dead_heartbeat(store, proxies, account_id, folder_id, time_dead):
    dead_time = time.time() - ALIVE_EXPIRY - time_dead
    dead_proxy = proxies[account_id][folder_id]
    store.publish(dead_proxy.key, dead_proxy.device_id,
                  json.dumps(dead_proxy.value), dead_time)


def test_get_all_heartbeats(random_heartbeats):
    accs = list_all_accounts()
    # the keys should be account IDs and the values should be True or False
    assert sorted(accs.keys()) == [str(i) for i in range(10)]
    assert all([isinstance(b, bool) for b in accs.values()])


def test_get_alive_dead_heartbeats(store, random_heartbeats):
    # kill an account by publishing one expired folder
    make_dead_heartbeat(store, random_heartbeats, 3, 1, 100)

    alive = list_alive_accounts()
    assert '3' not in alive

    dead = list_dead_accounts()
    assert dead == ['3']


def test_get_new_dead_heartbeats(store, random_heartbeats):
    # test the 'between' logic for checking newly-dead accounts
    make_dead_heartbeat(store, random_heartbeats, 7, -1, 100)
    make_dead_heartbeat(store, random_heartbeats, 2, -2, 1000)

    # All thresholds are in 'seconds before now'
    new_dead_threshold = ALIVE_EXPIRY + 500
    new_dead = list_dead_accounts(dead_since=new_dead_threshold)
    assert new_dead == ['7']

    old_dead = list_dead_accounts(dead_threshold=new_dead_threshold,
                                  dead_since=new_dead_threshold + 1000)
    assert old_dead == ['2']

    # The future is impossible
    wrong_threshold = ALIVE_EXPIRY / 2
    impossible_dead = list_dead_accounts(dead_since=wrong_threshold)
    assert impossible_dead == []


def test_count_heartbeats(random_heartbeats):
    accounts = list_alive_accounts(count=True)
    assert accounts == 10


def test_summary_metrics(store, random_heartbeats):
    make_dead_heartbeat(store, random_heartbeats, 5, 2, 100)
    make_dead_heartbeat(store, random_heartbeats, 8, 0, 248)

    summary = heartbeat_summary()
    del summary['timestamp']
    assert summary == {
        'accounts': 10,
        'accounts_percent': '80.00%',
        'alive_accounts': 8,
        'dead_accounts': 2
    }


def test_account_metadata(store):
    proxy_for(1, 2)
    proxy_for(3, 4, 'foo@bar.com', 'eas')

    (email, provider) = get_account_metadata(account_id=1)
    assert email == 'test@test.com'
    assert provider == 'gmail'

    (email, provider) = get_account_metadata(account_id=3)
    assert email == 'foo@bar.com'
    assert provider == 'eas'


def test_get_full_status(store):
    proxy_for(1, 3)
    proxy_for(1, 7)
    proxy_for(1, -1)
    proxy_for(1, -2)

    time.sleep(0.5)
    status = get_heartbeat_status()

    assert status.keys() == [1]
    account = status[1]
    assert isinstance(account, AccountHeartbeatStatus)
    assert account.alive
    assert len(account.folders) == 4
    assert all([f.alive for f in account.folders])


def test_missing_status(store):
    status = get_heartbeat_status(account_id=12)
    assert status.keys() == [12]
    assert status[12].missing
    assert not status[12].alive
