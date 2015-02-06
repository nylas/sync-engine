from inbox.log import get_logger
from inbox.heartbeat.config import STATUS_DATABASE, get_redis_client
from inbox.heartbeat.status import HeartbeatStatusKey


def has_contacts_and_events(account_id):
    try:
        client = get_redis_client(STATUS_DATABASE)
        batch_client = client.pipeline()
        batch_client.exists(HeartbeatStatusKey.contacts(account_id))
        batch_client.exists(HeartbeatStatusKey.events(account_id))
        values = batch_client.execute()
        return (values[0], values[1])
    except Exception:
        log = get_logger()
        log.error('Error while reading the heartbeat status',
                  account_id=account_id,
                  exc_info=True)
        return (False, False)
