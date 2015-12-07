from collections import namedtuple
from datetime import timedelta
import time

from nylas.logging import get_logger
from inbox.heartbeat.config import ALIVE_EXPIRY
from inbox.heartbeat.store import HeartbeatStore


ALIVE_THRESHOLD = timedelta(seconds=ALIVE_EXPIRY)

log = get_logger()


# More lightweight statuses (dead/alive signals only) - placeholder name Pings
AccountPing = namedtuple('AccountPing', ['id', 'folders'])
FolderPing = namedtuple('FolderPing', ['id', 'alive', 'timestamp'])


def get_ping_status(host=None, port=6379, account_id=None,
                    threshold=ALIVE_EXPIRY):
    # Query the indexes and not the per-folder info for faster lookup.
    store = HeartbeatStore.store(host, port)
    now = time.time()
    expiry = now - threshold
    if account_id:
        # Get a single account's heartbeat
        folder_heartbeats = store.get_account_folders(account_id)
        folders = [FolderPing(int(aid), ts > expiry, ts)
                   for (aid, ts) in folder_heartbeats]
        account = AccountPing(account_id, folders)
        return {account_id: account}
    else:
        # Start from the account index
        account_heartbeats = store.get_account_list()
        accounts = {}
        # grab the folders from all accounts in one batch
        all_folder_heartbeats = store.get_accounts_folders(
            [aid for aid, ts in account_heartbeats])
        for i, (account_id, account_ts) in enumerate(account_heartbeats):
            account_id = int(account_id)
            folder_heartbeats = all_folder_heartbeats[i]
            folders = [FolderPing(int(aid), ts > expiry, ts)
                       for (aid, ts) in folder_heartbeats]
            account = AccountPing(account_id, folders)
            accounts[account_id] = account
        return accounts


def clear_heartbeat_status(account_id, folder_id=None, device_id=None,
                           host=None, port=None):
    # Clears the status for the account, folder and/or device.
    # Returns the number of folders cleared.
    store = HeartbeatStore.store(host, port)
    n = store.remove_folders(account_id, folder_id, device_id)
    return n
