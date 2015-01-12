from inbox.log import get_logger
from inbox.heartbeat.config import STATUS_DATABASE, get_redis_client
from inbox.heartbeat.status import HeartbeatStatusKey


def delete_device(account_id, device_id):
    try:
        client = get_redis_client(STATUS_DATABASE)
        batch_client = client.pipeline()
        for k in client.scan_iter(HeartbeatStatusKey.all_folders(account_id)):
            batch_client.hdel(k, device_id)
        batch_client.execute()
    except Exception:
        log = get_logger()
        log.error('Error while deleting the heartbeat status',
                  account_id=account_id,
                  device_id=device_id,
                  exc_info=True)


def has_contacts_and_events(account_id):
    try:
        client = get_redis_client(STATUS_DATABASE)
        batch_client = client.pipeline()
        batch_client.keys(HeartbeatStatusKey.contacts(account_id))
        batch_client.keys(HeartbeatStatusKey.events(account_id))
        values = batch_client.execute()
        return (len(values[0]) == 1, len(values[1]) == 1)
    except Exception:
        log = get_logger()
        log.error('Error while reading the heartbeat status',
                  account_id=account_id,
                  exc_info=True)
        return (False, False)
