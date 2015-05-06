import time
import gevent
from datetime import datetime

from sqlalchemy import asc, desc
from sqlalchemy.orm import joinedload
from inbox.api.kellogs import APIEncoder, encode
from inbox.models import Transaction
from inbox.models.session import session_scope
from inbox.models.util import transaction_objects


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

    # We want this guarantee: if you pass a timestamp for, say,
    # '2015-03-20 12:22:20', and you have multiple transactions immediately
    # prior, e.g.:
    # id | created_at
    # ---+-----------
    # 23 | 2015-03-20 12:22:19
    # 24 | 2015-03-20 12:22:19
    # 25 | 2015-03-20 12:22:19
    # then you get the last one by id (25). Otherwise you might pass a
    # timestamp far in the future, but not actually get the last cursor.
    # The obvious way to accomplish this is to filter by `created_at` but order
    # by `id`. However, that causes MySQL to perform a potentially expensive
    # filesort. Instead, get transactions with timestamp *matching* the last
    # one before what you have, and sort those by id:
    latest_timestamp = db_session.query(Transaction.created_at). \
        order_by(desc(Transaction.created_at)). \
        filter(Transaction.created_at < dt,
               Transaction.namespace_id == namespace_id).limit(1).subquery()
    latest_transaction = db_session.query(Transaction). \
        filter(Transaction.created_at == latest_timestamp,
               Transaction.namespace_id == namespace_id). \
        order_by(desc(Transaction.id)).first()

    if latest_transaction is None:
        # If there are no earlier deltas, use '0' as a special stamp parameter
        # to signal 'process from the start of the log'.
        return '0'

    return latest_transaction.public_id


def format_transactions_after_pointer(namespace_id, pointer, db_session,
                                      result_limit, exclude_types=None):
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
    # deleted_at condition included to allow this query to be satisfied via
    # the legacy index on (namespace_id, deleted_at) for performance.
    # Also need to explicitly specify the index hint because the query
    # planner is dumb as nails and otherwise would make this super slow for
    # some values of namespace_id and pointer.
    # TODO(emfree): Remove this hack and ensure that the right index (on
    # namespace_id only) exists.
    transactions = db_session.query(Transaction). \
        filter(
            Transaction.id > pointer,
            Transaction.namespace_id == namespace_id,
            Transaction.deleted_at.is_(None)). \
        with_hint(Transaction, 'USE INDEX (namespace_id_deleted_at)')

    if exclude_types is not None:
        transactions = transactions.filter(
            ~Transaction.object_type.in_(exclude_types))

    transactions = transactions. \
        options(joinedload(Transaction.namespace)). \
        order_by(asc(Transaction.id)).limit(result_limit).all()

    if not transactions:
        return ([], pointer)

    deltas = []
    # If there are multiple transactions for the same object, only publish the
    # most recent.
    object_identifiers = set()
    for trx in sorted(transactions, key=lambda trx: trx.id, reverse=True):
        object_identifier = (trx.object_type, trx.record_id)
        if object_identifier in object_identifiers:
            continue

        object_identifiers.add(object_identifier)

        delta = {}
        if trx.command != 'delete':
            object_cls = transaction_objects()[trx.object_type]
            obj = db_session.query(object_cls).get(trx.record_id)
            if obj is None:
                continue
            delta['attributes'] = encode(
                obj, namespace_public_id=trx.namespace.public_id)

        if trx.command == 'insert':
            event = 'create'
        elif trx.command == 'update':
            event = 'modify'
        else:
            event = 'delete'

        delta.update({
            'object': trx.object_type,
            'event': event,
            'id': trx.object_public_id,
            'cursor': trx.public_id
        })
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
                exclude_types)
        if new_pointer is not None and new_pointer != transaction_pointer:
            transaction_pointer = new_pointer
            for delta in deltas:
                yield encoder.cereal(delta) + '\n'
        else:
            gevent.sleep(poll_interval)
