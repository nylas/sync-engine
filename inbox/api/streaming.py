import json
import time
import gevent
from sqlalchemy import desc
from inbox.models import Transaction
from inbox.models.session import session_scope


def get_latest_transaction_id(namespace_id):
    """Return the id of the latest transaction row for the given namespace."""
    with session_scope() as db_session:
        q = db_session.query(Transaction.id).filter(
            Transaction.namespace_id == namespace_id). \
            order_by(desc(Transaction.id))
        result = q.first()
        if result is None:
            return None
        return result[0]


def format_output(namespace_public_id):
    # Include a trailing newline for the benefit of clients who want to read
    # line-by-line.
    return json.dumps({'namespace_id': namespace_public_id}) + '\n'


def streaming_change_generator(namespace_id, namespace_public_id,
                               poll_interval, timeout,
                               transaction_pointer=None):
    """Poll the transaction log for the given `namespace_id` until `timeout`
    expires, and yield each time new entries are detected.
    Arguments
    ---------
    namespace_id: int
        Id of the namespace for which to check changes.
    namespace_public_id: string
        Public id of that namespace (to return in the response).
    poll_interval: float
        How often to check for changes.
    timeout: float
        How many seconds to allow the connection to remain open.
    transaction_pointer: int
        If given, only yield when transaction rows with id greater than
        `transaction_pointer` are found.
    """
    if transaction_pointer is None:
        transaction_pointer = get_latest_transaction_id(namespace_id)
    start_time = time.time()
    while time.time() - start_time < timeout:
        updated_pointer = get_latest_transaction_id(namespace_id)
        if (updated_pointer is not None and updated_pointer !=
                transaction_pointer):
            transaction_pointer = updated_pointer
            yield format_output(namespace_public_id)
        gevent.sleep(poll_interval)
