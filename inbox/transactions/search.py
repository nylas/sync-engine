import datetime
from collections import defaultdict
import calendar

from gevent import Greenlet, sleep

from inbox.log import get_logger
log = get_logger()
from inbox.api.kellogs import APIEncoder

from inbox.models.session import session_scope
from inbox.models.util import transaction_objects
from inbox.models.search import SearchIndexCursor
from inbox.search.adaptor import NamespaceSearchEngine
from inbox.transactions.delta_sync import format_transactions_after_pointer


class SearchIndexService(Greenlet):
    """
    Poll the transaction log for message, thread operations
    (inserts, updates, deletes) for all namespaces and perform the
    corresponding Elasticsearch index operations.

    """
    def __init__(self, poll_interval=30, chunk_size=100):
        self.poll_interval = poll_interval
        self.chunk_size = chunk_size

        self.encoder = APIEncoder()

        self.transaction_pointer = None

        self.log = log.new(component='search-index')
        Greenlet.__init__(self)

    def _run(self):
        """
        Index into Elasticsearch the threads, messages of all namespaces.

        """
        # Indexing is namespace agnostic.
        # Note that although this means we do not restrict the Transaction
        # table query (via the format_transactions_after_pointer() call below)
        # to a namespace, since we pass a `result_limit` (== chunk_size)
        # argument, the query should still be performant.
        namespace_id = None

        # Only index messages, threads.
        object_types = transaction_objects()
        exclude_types = [api_name for model_name, api_name in
                         object_types.iteritems() if model_name not in
                         ['message', 'thread']]

        with session_scope() as db_session:
            pointer = db_session.query(SearchIndexCursor).first()
            self.transaction_pointer = pointer.transaction_id if pointer else 0

        self.log.info('Starting search-index service',
                      transaction_pointer=self.transaction_pointer)

        while True:
            with session_scope() as db_session:
                deltas, new_pointer = format_transactions_after_pointer(
                    namespace_id, self.transaction_pointer, db_session,
                    self.chunk_size, _format_transaction_for_search,
                    exclude_types)

            # TODO[k]: We ideally want to index chunk_size at a time.
            # This currently indexes <= chunk_size, and it varies each time.
            if new_pointer is not None and \
                    new_pointer != self.transaction_pointer:

                self.index(deltas)
                self.update_pointer(new_pointer)
            else:
                sleep(self.poll_interval)

    def index(self, objects):
        """
        Translate database operations to Elasticsearch index operations
        and perform them.

        """
        namespace_map = defaultdict(lambda: defaultdict(list))

        for obj in objects:
            namespace_id = obj['namespace_id']
            type_ = obj['object']
            operation = obj['operation']
            api_repr = obj['attributes']

            namespace_map[namespace_id][type_].append((operation, api_repr))

        self.log.info('namespaces to index count', count=len(namespace_map))

        for namespace_id in namespace_map:
            engine = NamespaceSearchEngine(namespace_id)

            messages = namespace_map[namespace_id]['message']
            message_count = engine.messages.bulk_index(messages) if messages \
                else 0

            threads = namespace_map[namespace_id]['thread']
            thread_count = engine.threads.bulk_index(threads) if threads \
                else 0

            self.log.info('per-namespace index counts',
                          namespace_id=namespace_id,
                          message_count=message_count,
                          thread_count=thread_count)

    def update_pointer(self, new_pointer):
        """
        Persist transaction pointer to support restarts, update
        self.transaction_pointer.

        """
        with session_scope() as db_session:
            pointer = db_session.query(SearchIndexCursor).first()
            if pointer is None:
                pointer = SearchIndexCursor()
                db_session.add(pointer)

            pointer.transaction_id = new_pointer
            db_session.commit()

        self.transaction_pointer = new_pointer


def _format_transaction_for_search(transaction):
    # In order for Elasticsearch to do the right thing w.r.t
    # creating v/s. updating an index, the op_type must be set to
    # 'index'.
    if transaction.command in ['insert', 'update']:
        operation = 'index'
        attributes = transaction.snapshot
    else:
        operation = 'delete'
        attributes = dict(id=transaction.object_public_id)

    attributes = _process_attributes(attributes)

    delta = {
        'namespace_id': transaction.namespace.public_id,
        'object': transaction.object_type,
        'operation': operation,
        'id': transaction.object_public_id,
        'cursor': transaction.public_id,
        'attributes': attributes
    }

    return delta


def _process_attributes(source):
    """
    Convert the default datetime format to Unix timestamp format.
    So for example, 2014-12-11 00:07:06 is converted to 1418256426.

    """
    # Fields would be Message.date, Thread.last_message_timestamp,
    # Thread.first_message_timestamp
    for field, value in source.iteritems():
        if isinstance(value, datetime.datetime):
            source[field] = calendar.timegm(value.utctimetuple())

    return source
