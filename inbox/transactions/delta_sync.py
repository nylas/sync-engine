from datetime import datetime

from sqlalchemy import asc, desc
from sqlalchemy.orm.exc import NoResultFound

from inbox.models import Transaction


def create_events(transactions):
    events = []
    # If there are multiple transactions for the same object, only publish the
    # msot recent.
    object_identifiers = set()
    for transaction in sorted(transactions, key=lambda trx: trx.id,
                              reverse=True):
        object_identifier = (transaction.object_type, transaction.record_id)
        if object_identifier in object_identifiers:
            continue
        object_identifiers.add(object_identifier)
        event = {
            'object': transaction.object_type,
            'event': transaction.command,
            'id': transaction.object_public_id
        }
        if transaction.command != 'delete':
            event['attributes'] = transaction.snapshot
        events.append(event)
    return list(reversed(events))


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
    transactions = db_session.query(Transaction). \
        order_by(asc(Transaction.id)). \
        filter(Transaction.namespace_id == namespace_id,
               Transaction.id > internal_start_id).limit(result_limit).all()

    deltas = create_events(transactions)
    if transactions:
        cursor_end = transactions[-1].public_id
    else:
        cursor_end = cursor_start

    result = {
        'cursor_start': cursor_start,
        'deltas': deltas,
        'cursor_end': cursor_end
    }

    return result
