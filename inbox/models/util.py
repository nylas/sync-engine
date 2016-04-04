import time
import math
import gevent
import requests
import datetime
from collections import OrderedDict

from inbox.config import config
from inbox.models import Account
from inbox.util.stats import statsd_client
from inbox.models.session import session_scope
from nylas.logging.sentry import log_uncaught_errors
from inbox.heartbeat.status import clear_heartbeat_status
from inbox.models.session import session_scope_by_shard_id

from nylas.logging import get_logger

CHUNK_SIZE = 1000

log = get_logger()


def reconcile_message(new_message, session):
    """
    Check to see if the (synced) Message instance new_message was originally
    created/sent via the Inbox API (based on the X-Inbox-Uid header. If so,
    update the existing message with new attributes from the synced message
    and return it.

    """
    from inbox.models.message import Message

    if new_message.inbox_uid is None:
        # try to reconcile using other means
        q = session.query(Message).filter(
            Message.namespace_id == new_message.namespace_id,
            Message.data_sha256 == new_message.data_sha256)
        return q.first()

    if '-' not in new_message.inbox_uid:
        # Old X-Inbox-Id format; use the old reconciliation strategy.
        existing_message = session.query(Message).filter(
            Message.namespace_id == new_message.namespace_id,
            Message.inbox_uid == new_message.inbox_uid,
            Message.is_created).first()
        version = None
    else:
        # new_message has the new X-Inbox-Id format <public_id>-<version>
        # If this is an old version of a current draft, we want to:
        # * not commit a new, separate Message object for it
        # * not update the current draft with the old header values in the code
        #   below.
        expected_public_id, version = new_message.inbox_uid.split('-')
        existing_message = session.query(Message).filter(
            Message.namespace_id == new_message.namespace_id,
            Message.public_id == expected_public_id,
            Message.is_created).first()

    if existing_message is None:
        return None

    if version is None or int(version) == existing_message.version:
        existing_message.message_id_header = new_message.message_id_header
        existing_message.references = new_message.references
        # Non-persisted instance attribute used by EAS.
        existing_message.parsed_body = new_message.parsed_body

    return existing_message


def transaction_objects():
    """
    Return the mapping from API object name - which becomes the
    Transaction.object_type - for models that generate Transactions (i.e.
    models that implement the HasRevisions mixin).

    """
    from inbox.models import (Calendar, Contact, Message, Event, Block,
                              Category, Thread, Metadata)

    return {
        'calendar': Calendar,
        'contact': Contact,
        'draft': Message,
        'event': Event,
        'file': Block,
        'message': Message,
        'thread': Thread,
        'label': Category,
        'folder': Category,
        'account': Account,
        'metadata': Metadata
    }


def delete_marked_accounts(shard_id, throttle=False, dry_run=False):
    start = time.time()
    deleted_count = 0
    ids_to_delete = []

    with session_scope_by_shard_id(shard_id) as db_session:
        ids_to_delete = [(acc.id, acc.namespace.id) for acc
                         in db_session.query(Account) if acc.is_deleted]

    for account_id, namespace_id in ids_to_delete:
        try:
            with session_scope(namespace_id) as db_session:
                account = db_session.query(Account).get(account_id)
                if not account:
                    log.critical('Account with does not exist',
                                 account_id=account_id)
                    continue

                if account.sync_should_run or not account.is_deleted:
                    log.warn('Account NOT marked for deletion. '
                             'Will not delete', account_id=account_id)
                    continue

            log.info('Deleting account', account_id=account_id)
            start_time = time.time()
            # Delete data in database
            try:
                log.info('Deleting database data', account_id=account_id)
                delete_namespace(account_id, namespace_id, throttle=throttle,
                                 dry_run=dry_run)
            except Exception as e:
                log.critical('Database data deletion failed', error=e,
                             account_id=account_id)
                continue

            # Delete liveness data
            log.debug('Deleting liveness data', account_id=account_id)
            clear_heartbeat_status(account_id)
            deleted_count += 1
            statsd_client.timing('mailsync.account_deletion.queue.deleted',
                                 time.time() - start_time)
            gevent.sleep(60)
        except Exception:
            log_uncaught_errors(log, account_id=account_id)

    end = time.time()
    log.info('All data deleted successfully', shard_id=shard_id,
             time=end - start, count=deleted_count)


def delete_namespace(account_id, namespace_id, throttle=False, dry_run=False):
    """
    Delete all the data associated with a namespace from the database.
    USE WITH CAUTION.

    NOTE: This function is only called from bin/delete-account-data.
    It prints to stdout.

    """
    from inbox.ignition import engine_manager

    # Bypass the ORM for performant bulk deletion;
    # we do /not/ want Transaction records created for these deletions,
    # so this is okay.
    engine = engine_manager.get_for_id(namespace_id)

    # Chunk delete for tables that might have a large concurrent write volume
    # to prevent those transactions from blocking.
    # NOTE: ImapFolderInfo does not fall into this category but we include it
    # here for simplicity.

    filters = OrderedDict()

    for table in ['message', 'block', 'thread', 'transaction', 'actionlog',
                  'contact', 'event', 'dataprocessingcache']:
        filters[table] = ('namespace_id', namespace_id)

    with session_scope(namespace_id) as db_session:
        account = db_session.query(Account).get(account_id)
        if account.discriminator != 'easaccount':
            filters['imapuid'] = ('account_id', account_id)
            filters['imapfoldersyncstatus'] = ('account_id', account_id)
            filters['imapfolderinfo'] = ('account_id', account_id)
        else:
            filters['easuid'] = ('easaccount_id', account_id)
            filters['easfoldersyncstatus'] = ('account_id', account_id)

    for cls in filters:
        _batch_delete(engine, cls, filters[cls], throttle=throttle,
                      dry_run=dry_run)

    # Use a single delete for the other tables. Rows from tables which contain
    # cascade-deleted foreign keys to other tables deleted here (or above)
    # are also not always explicitly deleted, except where needed for
    # performance.
    #
    # NOTE: Namespace, Account are deleted at the end too.

    query = 'DELETE FROM {} WHERE {}={};'

    filters = OrderedDict()
    for table in ('category', 'calendar'):
        filters[table] = ('namespace_id', namespace_id)
    for table in ('folder', 'label'):
        filters[table] = ('account_id', account_id)
    filters['namespace'] = ('id', namespace_id)

    for table, (column, id_) in filters.iteritems():
        log.info('Performing bulk deletion', table=table)
        start = time.time()

        if throttle and check_throttle():
            log.info("Throttling deletion")
            gevent.sleep(60)

        if not dry_run:
            engine.execute(query.format(table, column, id_))
        else:
            log.debug(query.format(table, column, id_))

        end = time.time()
        log.info('Completed bulk deletion', table=table, time=end - start)

    # Delete the account object manually to get rid of the various objects
    # associated with it (e.g: secrets, tokens, etc.)
    with session_scope(account_id) as db_session:
        account = db_session.query(Account).get(account_id)
        if dry_run is False:
            db_session.delete(account)
            db_session.commit()


def _batch_delete(engine, table, xxx_todo_changeme, throttle=False,
                  dry_run=False):
    (column, id_) = xxx_todo_changeme
    count = engine.execute(
        'SELECT COUNT(*) FROM {} WHERE {}={};'.format(table, column, id_)).\
        scalar()

    if count == 0:
        log.info('Completed batch deletion', table=table)
        return

    batches = int(math.ceil(float(count) / CHUNK_SIZE))

    log.info('Starting batch deletion', table=table, count=count,
             batches=batches)
    start = time.time()

    query = 'DELETE FROM {} WHERE {}={} LIMIT 20000;'.format(
        table, column, id_)

    pruned_messages = False
    for i in range(0, batches):
        if throttle and check_throttle():
            log.info("Throttling deletion")
            gevent.sleep(60)
        if dry_run is False:
            if table == "message" and not pruned_messages:
                if engine.execute("SELECT EXISTS(SELECT id FROM message WHERE "
                                  "{}={} AND reply_to_message_id IS NOT NULL);"
                                  .format(column, id_)).scalar():
                    query = ('DELETE FROM message WHERE {}={} AND '
                             'reply_to_message_id IS NOT NULL LIMIT 2000;'
                             .format(column, id_))
                else:
                    pruned_messages = True
            engine.execute(query)
        else:
            log.debug(query)

    end = time.time()
    log.info('Completed batch deletion', time=end - start, table=table)


def check_throttle():
    # Ensure replica lag is not spiking
    base_url = config["UMPIRE_BASE_URL"]
    replica_lag_url = ("https://{}/check?metric=maxSeries(servers.prod."
                       "sync-mysql-node.*.mysql.Seconds_Behind_Master)"
                       "&max=10&min=0&range=300".format(base_url))

    cpu_url = ('https://{}/check?metric=maxSeries(offset(scale(groupByNode('
               'servers.prod.sync-mysql-node.*.cpu.cpu*.idle,3,'
               '"averageSeries"),-1),100))&max=70&min=0&range=300'.
               format(base_url))

    replica_lag_status_code = requests.get(replica_lag_url).status_code
    cpu_status_code = requests.get(cpu_url).status_code
    if replica_lag_status_code != 200 or cpu_status_code != 200:
        return True

    # Stop deletion before backups are scheduled to start(1am UTC)
    # and resume when backups complete (~9:30am, but set to 10am to
    # leave room for error)
    now = datetime.datetime.utcnow()
    if now.hour < 10:
        return True
