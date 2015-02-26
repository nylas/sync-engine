from datetime import datetime, timedelta
import json
import time

from inbox.log import get_logger
from inbox.heartbeat.config import ALIVE_EXPIRY
from inbox.heartbeat.store import HeartbeatStore, HeartbeatStatusKey


ALIVE_THRESHOLD = timedelta(seconds=ALIVE_EXPIRY)

log = get_logger()


class DeviceHeartbeatStatus(object):
    alive = True
    state = None
    heartbeat_at = None

    def __init__(self, device_id, device_status, threshold=ALIVE_THRESHOLD):
        self.id = device_id
        self.heartbeat_at = datetime.strptime(device_status['heartbeat_at'],
                                              '%Y-%m-%d %H:%M:%S.%f')
        self.state = device_status.get('state', None)
        time_since_heartbeat = (datetime.utcnow() - self.heartbeat_at)
        self.alive = time_since_heartbeat < threshold
        self.action = device_status.get('action', None)

    def jsonify(self):
        return {'alive': self.alive,
                'state': self.state,
                'action': self.action,
                'heartbeat_at': str(self.heartbeat_at)}


class FolderHeartbeatStatus(object):
    alive = True
    name = ''
    email_address = ''
    provider_name = ''

    def __init__(self, folder_id, folder_status, threshold=ALIVE_THRESHOLD):
        """ Initialize a FolderHeartbeatStatus from a folder status dictionary
            containing individual device reports for that folder.
        """
        self.id = folder_id
        self.devices = {}
        for device_id, device_status in folder_status.iteritems():
            self.email_address = device_status['email_address']
            self.provider_name = device_status['provider_name']
            self.name = device_status['folder_name']
            device = DeviceHeartbeatStatus(device_id, device_status, threshold)
            self.devices[device_id] = device
            # a folder is alive iff all the devices handling it are alive
            self.alive = self.alive and device.alive

    @property
    def initial_sync(self):
        return any(device.state == 'initial'
                   for device in self.devices.itervalues())

    @property
    def poll_sync(self):
        return all(device.state == 'poll'
                   for device in self.devices.itervalues())

    def jsonify(self):
        return {'alive': self.alive,
                'name': self.name,
                'devices': {device_id: device.jsonify()
                            for device_id, device in self.devices.iteritems()}}


class AccountHeartbeatStatus(object):
    email_address = ''
    provider_name = ''
    id = None

    def __init__(self, id, missing=False):
        # 'missing' denotes a heartbeat that was explicitly checked for and
        # not found. on initialization, a missing heartbeat should not be
        # defaulted to alive, but all other heartbeats should be.
        self.id = id
        self.missing = missing
        self._folders = {}
        if missing:
            self.alive = False
        else:
            self.alive = True

    def add_folder(self, folder):
        self._folders[folder.id] = folder
        # email and provider are stored in folder heartbeats since we don't
        # send per-account heartbeats, so update the account metadata here.
        if folder.email_address:
            self.email_address = folder.email_address
        if folder.provider_name:
            self.provider_name = folder.provider_name
        # Update alive state: alive only iff all folders are alive.
        self.alive = self.alive and folder.alive

    def get_timestamp(self):
        store = HeartbeatStore.store()
        store.get_account_timestamp(self.id)

    @property
    def folders(self):
        return self._folders.values()

    @property
    def dead_folders(self):
        return [folder.name
                for folder in self.folders if not folder.alive]

    @property
    def initial_sync(self):
        return any(folder.initial_sync for folder in self.folders)

    @property
    def poll_sync(self):
        return all(folder.poll_sync for folder in self.folders)

    def __repr__(self):
        return "<AccountHeartbeatStatus: Account {}: {}>".format(
            self.id, self.alive)

    def jsonify(self):
        return {'missing': self.missing,
                'alive': self.alive,
                'email_address': self.email_address,
                'provider_name': self.provider_name,
                'folders': {folder.id: folder.jsonify()
                            for folder in self.folders}}


def load_folder_status(k, v):
    folder = {}
    for device_id in v:
        folder[int(device_id)] = json.loads(v[device_id])
    return folder


def get_heartbeat_status(host=None, port=6379, account_id=None):
    # Gets the full (folder-by-folder) heartbeat status report for all
    # accounts or a specific account ID.
    store = HeartbeatStore.store(host, port)
    folders = store.get_folders(load_folder_status, account_id)
    accounts = {}
    for composite_key, folder in folders.iteritems():
        # Unwrap the folder reports from Redis into AccountHeartbeatStatus
        key = HeartbeatStatusKey.from_string(composite_key)
        account = accounts.get(key.account_id,
                               AccountHeartbeatStatus(key.account_id))
        # Update accounts list by adding folder heartbeat.
        folder_hb = FolderHeartbeatStatus(key.folder_id, folder,
                                          ALIVE_THRESHOLD)
        account.add_folder(folder_hb)
        accounts[key.account_id] = account

    if account_id and account_id not in accounts:
        # If we asked about a specific folder and it didn't come back,
        # report it as missing.
        accounts[account_id] = AccountHeartbeatStatus(account_id, missing=True)

    return accounts


def get_account_timestamps(host=None, port=6379, account_id=None):
    store = HeartbeatStore.store(host, port)
    if account_id:
        return [(account_id, store.get_account_timestamp(account_id))]
    else:
        return store.get_account_list()


def get_account_summary(host=None, port=6379, account_id=None):
    if not account_id:
        return []
    store = HeartbeatStore.store(host, port)
    folders = store.get_account_folders(account_id)
    return folders


def get_account_metadata(host=None, port=6379, account_id=None):
    # Get account metadata (email, provider) from a folder entry.
    if not account_id:
        return
    store = HeartbeatStore.store(host, port)
    folder_id, folder_hb = store.get_single_folder(account_id)
    folder = FolderHeartbeatStatus(folder_id,
                                   load_folder_status(folder_id, folder_hb))
    return (folder.email_address, folder.provider_name)


def list_alive_accounts(host=None, port=None, alive_since=ALIVE_EXPIRY,
                        count=False, timestamps=False):
    # List accounts that have checked in during the last alive_since seconds.
    # Returns a list of account IDs.
    # If `count` is specified, returns count.
    # If `timestamps` specified, returns (account_id, timestamp) tuples.
    store = HeartbeatStore.store(host, port)
    if count:
        return store.count_accounts(alive_since)
    else:
        accounts = store.get_account_list(alive_since)
    if timestamps:
        return accounts
    return [a for a, ts in accounts]


def list_dead_accounts(host=None, port=None, dead_threshold=ALIVE_EXPIRY,
                       dead_since=None, count=False, timestamps=False):
    # List accounts that haven't checked in for dead_threshold seconds.
    # Optionally, provide dead_since to find accounts whose last
    # checkin time was after dead_since seconds ago.
    # Returns a list of account IDs.
    # If `count` is specified, returns count.
    # If `timestamps` specified, returns (account_id, timestamp) tuples.
    store = HeartbeatStore.store(host, port)
    if dead_since:
        if count:
            return store.count_accounts(dead_since, dead_threshold)
        else:
            accounts = store.get_accounts_between(dead_since, dead_threshold)
    else:
        if count:
            return store.count_accounts(dead_threshold, above=False)
        else:
            accounts = store.get_accounts_below(dead_threshold)
    if timestamps:
        return accounts
    return [a for a, ts in accounts]


def list_all_accounts(host=None, port=None, dead_threshold=ALIVE_EXPIRY,
                      timestamps=False):
    # List all accounts with true/false heartbeats if alive or not.
    # If `timestamps` specified, returns (alive_or_not, timestamp) tuples.
    threshold = time.time() - dead_threshold
    store = HeartbeatStore.store(host, port)
    accounts = store.get_account_list()
    heartbeats = {}
    for (account, ts) in accounts:
        if timestamps:
            heartbeats[account] = (ts > threshold, ts)
        else:
            heartbeats[account] = ts > threshold
    return heartbeats


def heartbeat_summary(host=None, port=None, dead_threshold=ALIVE_EXPIRY):
    num_dead_accounts = list_dead_accounts(host, port,
                                           dead_threshold=dead_threshold,
                                           count=True)
    num_alive_accounts = list_alive_accounts(host, port, 
                                            alive_since=dead_threshold,
                                            count=True)
    num_accounts = num_alive_accounts + num_dead_accounts
    if num_alive_accounts:
        accounts_percent = float(num_alive_accounts) / num_accounts
    else:
        accounts_percent = 0
    status = {
        'accounts': num_accounts,
        'accounts_percent': "{:.2%}".format(accounts_percent),
        'alive_accounts': num_alive_accounts,
        'dead_accounts': num_dead_accounts,
        'timestamp': datetime.strftime(datetime.utcnow(), '%H:%M:%S %b %d, %Y')
    }
    return status


def clear_heartbeat_status(account_id, folder_id=None, device_id=None,
                           host=None, port=None):
    # Clears the status for the account, folder and/or device.
    # Returns the number of folders cleared.
    store = HeartbeatStore.store(host, port)
    n = store.remove_folders(account_id, folder_id, device_id)
    return n
