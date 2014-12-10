import time
import gevent
from datetime import datetime

from sqlalchemy import asc, desc
from inbox.api.kellogs import APIEncoder
from inbox.models import Transaction
from inbox.models.session import session_scope


def get_transaction_cursor_near_timestamp(namespace_id, timestamp, db_session):
    """
    Exchange a timestamp for a 'cursor' into the transaction log entry near
    to that timestamp in age. The cursor is the public_id of that transaction
    (or '0' if there are no such transactions).

    Arguments
    ---------
    namespace_id: int
        Id of the namespace for which to get a cursor.
    timestamp: int
        Unix timestamp
    db_session: InboxSession
        database session

    Returns
    -------
    string
        A transaction public_id that can be passed as a 'cursor' parameter by
        API clients.

    """
    dt = datetime.utcfromtimestamp(timestamp)
    transaction = db_session.query(Transaction). \
        order_by(desc(Transaction.id)). \
        filter(Transaction.created_at < dt,
               Transaction.namespace_id == namespace_id).first()
    if transaction is None:
        # If there are no earlier deltas, use '0' as a special stamp parameter
        # to signal 'process from the start of the log'.
        return '0'
    return transaction.public_id


def format_transactions_after_pointer(namespace_id, pointer, db_session,
                                      result_limit, format_transaction_fn,
                                      exclude_types=None):
    """
    Return a pair (deltas, new_pointer), where deltas is a list of change
    events, represented as dictionaries:
    {
      "object": <API object type, e.g. "thread">,
      "event": <"create", "modify", or "delete>,
      "attributes": <API representation of the object for insert/update events>
      "cursor": <public_id of the transaction>
    }

    and new_pointer is the integer id of the last included transaction

    Arguments
    ---------
    namespace_id: int
        Id of the namespace for which to get changes.
    pointer: int
        Process transactions starting after this id.
    db_session: InboxSession
        database session
    result_limit: int
        Maximum number of results to return. (Because we may roll up multiple
        changes to the same object, fewer results can be returned.)
    format_transaction_fn: function pointer
        Function that defines how to format the transactions.
    exclude_types: list, optional
        If given, don't include transactions for these types of objects.

    """
    filters = [Transaction.id > pointer]

    if namespace_id is not None:
        filters.append(Transaction.namespace_id == namespace_id)

    if exclude_types is not None:
        filters.append(~Transaction.object_type.in_(exclude_types))

    transactions = db_session.query(Transaction). \
        order_by(asc(Transaction.id)). \
        filter(*filters).limit(result_limit)

    transactions = transactions.all()

    if not transactions:
        return ([], pointer)

    deltas = []
    # If there are multiple transactions for the same object, only publish the
    # most recent.
    # Note: Works as is even when we're querying across all namespaces (i.e.
    # namespace_id = None) because the object is identified by its id in
    # addition to type, and all objects are restricted to a single namespace.
    object_identifiers = set()
    for transaction in sorted(transactions, key=lambda trx: trx.id,
                              reverse=True):
        object_identifier = (transaction.object_type, transaction.record_id)
        if object_identifier in object_identifiers:
            continue

        object_identifiers.add(object_identifier)
        delta = format_transaction_fn(transaction)
        deltas.append(delta)

    return (list(reversed(deltas)), transactions[-1].id)


def streaming_change_generator(namespace_id, poll_interval, timeout,
                               transaction_pointer, exclude_types=None):
    """
    Poll the transaction log for the given `namespace_id` until `timeout`
    expires, and yield each time new entries are detected.
    Arguments
    ---------
    namespace_id: int
        Id of the namespace for which to check changes.
    poll_interval: float
        How often to check for changes.
    timeout: float
        How many seconds to allow the connection to remain open.
    transaction_pointer: int, optional
        Yield transaction rows starting after the transaction with id equal to
        `transaction_pointer`.

    """
    encoder = APIEncoder()
    start_time = time.time()
    while time.time() - start_time < timeout:
        with session_scope() as db_session:
            deltas, new_pointer = format_transactions_after_pointer(
                namespace_id, transaction_pointer, db_session, 100,
                _format_transaction_for_delta_sync, exclude_types)
        if new_pointer is not None and new_pointer != transaction_pointer:
            transaction_pointer = new_pointer
            for delta in deltas:
                yield encoder.cereal(delta) + '\n'
        else:
            gevent.sleep(poll_interval)


def _format_transaction_for_delta_sync(transaction):
    if transaction.command == 'insert':
        event = 'create'
    elif transaction.command == 'update':
        event = 'modify'
    else:
        event = 'delete'
    delta = {
        'object': transaction.object_type,
        'event': event,
        'id': transaction.object_public_id,
        'cursor': transaction.public_id
    }
    if transaction.command != 'delete':
        delta['attributes'] = transaction.snapshot
    return delta
