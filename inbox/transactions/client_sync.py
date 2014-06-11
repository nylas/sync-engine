from datetime import datetime

from sqlalchemy import asc, desc
from sqlalchemy.orm.exc import NoResultFound

from inbox.models.tables.base import Transaction


def dict_delta(current_dict, previous_dict):
    """Return a dictionary consisting of the key-value pairs in
    current_dict that differ from those in previous_dict."""
    return {k: v for k, v in current_dict.iteritems() if k not in previous_dict
            or previous_dict[k] != v}


def should_publish_transaction(transaction, db_session):
    """Returns True if the given transaction contains should actually be
    published by the client sync API."""
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
        order_by(asc(Transaction.id)). \
        filter(Transaction.created_at >= dt,
               Transaction.namespace_id == namespace_id).first()
    if transaction is None:
        return None
    return transaction.public_id


def get_entries_from_public_id(namespace_id, events_start, db_session,
                               result_limit):
    """Returns up to result_limit processed transaction log entries for the
    given namespace_id. Begins processing the log at the transaction with
    public_id equal to the events_start parameter.

    Arguments
    ---------
    namespace_id: int
    events_start: string
        The public_id of the transaction log entry at which to begin
        processing. Normally this should be the return value of a previous call
        to get_public_id_from_ts, or the value of 'next_event' from a previous
        call to this function.
    db_session: InboxSession
    result_limit: int
        The maximum number of events to return.

    Returns
    -------
    Dictionary with keys:
     - 'events_start'
     - 'events': list of serialized add/modify/delete events
     - (optional) 'next_event': the public_id of the next transaction log entry
       after the returned events, if available. This value can be passed as
       events_start in a subsequent call to this function to get the next page
       of results.

    Raises
    ------
    ValueError
        If events_start is not a valid public_id of a transaction entry for
        the given namespace.
    """
    try:
        # Check that events_start could be a public id
        int(events_start, 36)
        internal_start_id, = db_session.query(Transaction.id). \
            filter(Transaction.public_id == events_start,
                   Transaction.namespace_id == namespace_id).one()
    except (ValueError, NoResultFound):
        raise ValueError('Invalid first_public_id parameter: {}'.
                         format(events_start))
    query = db_session.query(Transaction). \
        order_by(asc(Transaction.id)). \
        filter(Transaction.namespace_id == namespace_id,
               Transaction.id >= internal_start_id)
    events = []
    next_event = None
    for transaction in query.yield_per(result_limit):

        if should_publish_transaction(transaction, db_session):
            event = create_event(transaction)
            if len(events) == result_limit:
                next_event = transaction.public_id
                break
            events.append(event)

    result = {
        'events_start': events_start,
        'events': events
    }
    # Only return a next_event value if there are more transactions available.
    if next_event is not None:
        result['next_event'] = next_event
    return result
