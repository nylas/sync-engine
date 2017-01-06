import json
from datetime import datetime

from sqlalchemy import asc
from sqlalchemy.sql import func
from sqlalchemy.orm import joinedload
from gevent import Greenlet, sleep

from inbox.ignition import engine_manager
from inbox.util.itert import partition
from inbox.models import Transaction, Contact
from inbox.util.stats import statsd_client
from inbox.models.session import session_scope_by_shard_id
from inbox.models.search import ContactSearchIndexCursor
from inbox.contacts.search import (get_doc_service, DOC_UPLOAD_CHUNK_SIZE,
                                   cloudsearch_contact_repr)

from nylas.logging import get_logger
from nylas.logging.sentry import log_uncaught_errors

log = get_logger()


class ContactSearchIndexService(Greenlet):
    """
    Poll the transaction log for contact operations
    (inserts, updates, deletes) for all namespaces and perform the
    corresponding CloudSearch index operations.

    """

    def __init__(self, poll_interval=30, chunk_size=DOC_UPLOAD_CHUNK_SIZE):
        self.poll_interval = poll_interval
        self.chunk_size = chunk_size
        self.transaction_pointers = {}

        self.log = log.new(component='contact-search-index')
        Greenlet.__init__(self)

    def _report_batch_upload(self):
        metric_names = [
            "contacts_search_index.transactions.batch_upload",
        ]

        for metric in metric_names:
            statsd_client.incr(metric)

    def _report_transactions_latency(self, latency):
        metric_names = [
            "contacts_search_index.transactions.latency",
        ]

        for metric in metric_names:
            statsd_client.timing(metric, latency)

    def _publish_heartbeat(self):
        metric_names = [
            "contacts_search_index.heartbeat",
        ]

        for metric in metric_names:
            statsd_client.incr(metric)

    def _set_transaction_pointers(self):
        for key in engine_manager.engines:
            with session_scope_by_shard_id(key) as db_session:
                pointer = db_session.query(
                    ContactSearchIndexCursor).first()
                if pointer:
                    self.transaction_pointers[key] = pointer.transaction_id
                else:
                    # Never start from 0; if the service hasn't run before
                    # start from the latest transaction, with the expectation
                    # that a backfill will be run separately.
                    max_id = db_session.query(
                        func.max(Transaction.id)).scalar() or 0
                    latest_transaction = \
                        db_session.query(Transaction).get(max_id)
                    if latest_transaction:
                        self.transaction_pointers[
                            key] = latest_transaction.id
                    else:
                        self.transaction_pointers[key] = 0

    def _index_transactions(self, namespace_ids=[]):
        """ index with filter """
        # index 'em
        for key in engine_manager.engines:
            shard_should_sleep = []
            with session_scope_by_shard_id(key) as db_session:
                txn_query = db_session.query(Transaction).filter(
                    Transaction.id > self.transaction_pointers[key],
                    Transaction.object_type == 'contact')
                if namespace_ids:
                    txn_query = txn_query.filter(
                        Transaction.namespace_id.in_(
                            namespace_ids))
                transactions = txn_query\
                    .order_by(asc(Transaction.id)) \
                    .limit(self.chunk_size).all()

                # index up to chunk_size transactions
                should_sleep = False
                if transactions:
                    self.index(transactions, db_session)
                    oldest_transaction = min(
                        transactions, key=lambda t: t.created_at)
                    current_timestamp = datetime.utcnow()
                    latency = (current_timestamp -
                               oldest_transaction.created_at).seconds
                    self._report_transactions_latency(latency)
                    new_pointer = transactions[-1].id
                    self.update_pointer(new_pointer, key, db_session)
                    db_session.commit()
                else:
                    should_sleep = True
            shard_should_sleep.append(should_sleep)
        if all(shard_should_sleep):
            log.info('sleeping')
            sleep(self.poll_interval)

    def _run(self):
        """
        Index into CloudSearch the contacts of all namespaces.

        """
        try:
            self._set_transaction_pointers()

            self.log.info('Starting contact-search-index service',
                          transaction_pointers=self.transaction_pointers)

            while True:
                self._publish_heartbeat()
                self._index_transactions()

        except Exception:
            log_uncaught_errors(log)

    def index(self, transactions, db_session):
        """
        Translate database operations to CloudSearch index operations
        and perform them.

        """
        docs = []
        doc_service = get_doc_service()
        add_txns, delete_txns = partition(
            lambda trx: trx.command == 'delete', transactions)
        delete_docs = [{'type': 'delete', 'id': txn.record_id}
                       for txn in delete_txns]
        add_record_ids = [txn.record_id for txn in add_txns]
        add_records = db_session.query(Contact).options(
            joinedload("phone_numbers")).filter(
                Contact.id.in_(add_record_ids))
        add_docs = [{'type': 'add', 'id': obj.id,
                     'fields': cloudsearch_contact_repr(obj)}
                    for obj in add_records]
        docs = delete_docs + add_docs

        if docs:
            doc_service.upload_documents(
                documents=json.dumps(docs),
                contentType='application/json')
            self._report_batch_upload()

        self.log.info('docs indexed', adds=len(add_docs),
                      deletes=len(delete_docs))

    def update_pointer(self, new_pointer, shard_key, db_session):
        """
        Persist transaction pointer to support restarts, update
        self.transaction_pointer.

        """
        pointer = db_session.query(ContactSearchIndexCursor).first()
        if pointer is None:
            pointer = ContactSearchIndexCursor()
            db_session.add(pointer)
        pointer.transaction_id = new_pointer
        self.transaction_pointers[shard_key] = new_pointer
