from datetime import datetime

from sqlalchemy import asc, desc
from sqlalchemy.orm.exc import NoResultFound

from inbox.models import Transaction
from inbox.sqlalchemy_ext.util import safer_yield_per


def dict_delta(current_dict, previous_dict):
    """Return a dictionary consisting of the key-value pairs in
    current_dict that differ from those in previous_dict."""
    return {k: v for k, v in current_dict.iteritems() if k not in previous_dict
            or previous_dict[k] != v}


def should_publish_transaction(transaction, db_session):
    """Returns True if the given transaction should actually be published by
    the client sync API."""
    if transaction.object_public_id is None:
        return False
    if 'object' not in transaction.public_snapshot:
        return False
    if transaction.command == 'update':
        # Don't publish transactions if they don't result in publicly-visible
        # changes.
        prev_revision = db_session.query(Transaction). \
            filter(Transaction.table_name == transaction.table_name,
                   Transaction.record_id == transaction.record_id,
                   Transaction.namespace_id == transaction.namespace_id,
                   Transaction.id < transaction.id). \
            order_by(desc(Transaction.id)).first()

        if (prev_revision is not None and prev_revision.public_snapshot is not
                None):
            public_delta = dict_delta(transaction.public_snapshot,
                                      prev_revision.public_snapshot)
            if not public_delta:
                return False
    if (transaction.public_snapshot.get('object') == 'file' and
            transaction.public_snapshot.get('filename') is None):
        # Don't publish transactions on Parts/Blocks if they're really just raw
        # message parts.
        return False
    return True


def create_event(transaction):
    """Returns a dictionary representing the JSON object that should be
    returned to the client for this transaction, or returns None if there are
    no changes to expose."""
    result = {}

    result['id'] = transaction.object_public_id
    result['object_type'] = transaction.public_snapshot.get('object')

    if transaction.command == 'delete':
        result['event'] = 'delete'
    elif (transaction.delta is not None and transaction.delta.get('deleted_at')
          is not None):
        # Object was soft-deleted
        result['event'] = 'delete'
    elif transaction.command == 'insert':
        result['event'] = 'create'
        result['attributes'] = transaction.public_snapshot
    elif transaction.command == 'update':
        result['event'] = 'update'
        result['attributes'] = transaction.public_snapshot

    return result


def get_public_id_from_ts(namespace_id, timestamp, db_session):
    """Return the public_id of the first transaction with given namespace_id
    after the given timestamp.

    Arguments
    ---------
    namespace_id: int
    timestamp: int
        Unix timestamp
    db_session: InboxSession
        database session

    Returns
    -------
    string
        A transaction public_id that can be passed as a 'stamp' parameter by
        API clients, or None if there is no such public id.
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


def get_entries_from_public_id(namespace_id, cursor_start, db_session,
                               result_limit):
    """Returns up to result_limit processed transaction log entries for the
    given namespace_id. Begins processing the log after the transaction with
    public_id equal to the cursor_start parameter.

    Arguments
    ---------
    namespace_id: int
    cursor_start: string
        The public_id of the transaction log entry after which to begin
        processing. Normally this should be the return value of a previous call
        to get_public_id_from_ts, or the value of 'cursor_end' from a previous
        call to this function.
    db_session: InboxSession
    result_limit: int
        The maximum number of deltas to return.

    Returns
    -------
    Dictionary with keys:
     - 'cursor_start'
     - 'deltas': list of serialized add/modify/delete deltas
     - (optional) 'cursor_end': the public_id of the last transaction log entry
       in the returned deltas, if available. This value can be passed as
       cursor_start in a subsequent call to this function to get the next page
       of results.

    Raises
    ------
    ValueError
        If cursor_start is invalid.
    """
    try:
        # Check that cursor_start can be a public id, and interpret the special
        # stamp value '0'.
        int_value = int(cursor_start, 36)
        if not int_value:
            internal_start_id = 0
        else:
            internal_start_id, = db_session.query(Transaction.id). \
                filter(Transaction.public_id == cursor_start,
                       Transaction.namespace_id == namespace_id).one()
    except (ValueError, NoResultFound):
        raise ValueError('Invalid first_public_id parameter: {}'.
                         format(cursor_start))
    query = db_session.query(Transaction). \
        order_by(asc(Transaction.id)). \
        filter(Transaction.namespace_id == namespace_id)

    deltas = []
    cursor_end = cursor_start
    for transaction in safer_yield_per(query, Transaction.id,
                                       internal_start_id + 1,
                                       result_limit):

        if should_publish_transaction(transaction, db_session):
            event = create_event(transaction)
            deltas.append(event)
            cursor_end = transaction.public_id
            if len(deltas) == result_limit:
                break

    result = {
        'cursor_start': cursor_start,
        'deltas': deltas,
        'cursor_end': cursor_end
    }

    return result
