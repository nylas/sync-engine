from collections import defaultdict
from sqlalchemy import asc, or_
from sqlalchemy.orm import joinedload
from gevent import Greenlet, sleep

from inbox.log import get_logger
log = get_logger()
from inbox.api.kellogs import encode
from inbox.models import Transaction
from inbox.models.session import session_scope
from inbox.models.util import transaction_objects
from inbox.models.search import SearchIndexCursor
from inbox.search.adaptor import NamespaceSearchEngine


class SearchIndexService(Greenlet):
    """
    Poll the transaction log for message, thread operations
    (inserts, updates, deletes) for all namespaces and perform the
    corresponding Elasticsearch index operations.

    """
    def __init__(self, poll_interval=30, chunk_size=100):
        self.poll_interval = poll_interval
        self.chunk_size = chunk_size
        self.transaction_pointer = None

        self.log = log.new(component='search-index')
        Greenlet.__init__(self)

    def _run(self):
        """
        Index into Elasticsearch the threads, messages of all namespaces.

        """
        with session_scope() as db_session:
            pointer = db_session.query(SearchIndexCursor).first()
            self.transaction_pointer = pointer.transaction_id if pointer else 0

        self.log.info('Starting search-index service',
                      transaction_pointer=self.transaction_pointer)

        while True:
            with session_scope() as db_session:
                transactions = db_session.query(Transaction). \
                    filter(Transaction.id > self.transaction_pointer,
                           or_(Transaction.object_type == 'message',
                               Transaction.object_type == 'thread')). \
                    order_by(asc(Transaction.id)). \
                    limit(self.chunk_size). \
                    options(joinedload(Transaction.namespace)).all()

                # TODO[k]: We ideally want to index chunk_size at a time.
                # This currently indexes <= chunk_size, and it varies each
                # time.
                if transactions:
                    self.index(transactions, db_session)
                    new_pointer = transactions[-1].id
                    self.update_pointer(new_pointer, db_session)
                else:
                    sleep(self.poll_interval)
                db_session.commit()

    def index(self, transactions, db_session):
        """
        Translate database operations to Elasticsearch index operations
        and perform them.

        """
        namespace_map = defaultdict(lambda: defaultdict(list))

        for trx in transactions:
            namespace_id = trx.namespace.public_id
            type_ = trx.object_type
            if trx.command == 'delete':
                operation = 'delete'
                api_repr = {'id': trx.object_public_id}
            else:
                operation = 'index'
                object_cls = transaction_objects()[trx.object_type]
                obj = db_session.query(object_cls).get(trx.record_id)
                if obj is None:
                    continue
                api_repr = encode(obj, namespace_public_id=namespace_id)

            namespace_map[namespace_id][type_].append((operation, api_repr))

        self.log.info('namespaces to index count', count=len(namespace_map))

        for namespace_id in namespace_map:
            engine = NamespaceSearchEngine(namespace_id, create_index=True)

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

    def update_pointer(self, new_pointer, db_session):
        """
        Persist transaction pointer to support restarts, update
        self.transaction_pointer.

        """
        pointer = db_session.query(SearchIndexCursor).first()
        if pointer is None:
            pointer = SearchIndexCursor()
            db_session.add(pointer)
        pointer.transaction_id = new_pointer
        self.transaction_pointer = new_pointer
