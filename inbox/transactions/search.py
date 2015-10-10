import json

from sqlalchemy import asc, desc
from sqlalchemy.orm import joinedload
from gevent import Greenlet, sleep

from inbox.util.itert import partition
from inbox.models import Transaction, Contact
from inbox.models.session import session_scope
from inbox.models.search import ContactSearchIndexCursor
from inbox.contacts.search import (get_doc_service, DOC_UPLOAD_CHUNK_SIZE,
                                   cloudsearch_contact_repr)

from nylas.logging import get_logger
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
        self.transaction_pointer = None

        self.log = log.new(component='contact-search-index')
        Greenlet.__init__(self)

    def _run(self):
        """
        Index into CloudSearch the contacts of all namespaces.

        """
        with session_scope() as db_session:
            pointer = db_session.query(ContactSearchIndexCursor).first()
            if pointer:
                self.transaction_pointer = pointer.transaction_id
            else:
                # Never start from 0; if the service hasn't run before start
                # from the latest transaction, with the expectation that a
                # backfill will be run separately.
                latest_transaction = db_session.query(Transaction).order_by(
                    desc(Transaction.created_at)).first()
                self.transaction_pointer = latest_transaction.id

        self.log.info('Starting contact-search-index service',
                      transaction_pointer=self.transaction_pointer)

        while True:
            with session_scope() as db_session:
                transactions = db_session.query(Transaction). \
                    filter(Transaction.id > self.transaction_pointer,
                           Transaction.object_type == 'contact'). \
                    with_hint(Transaction,
                              "USE INDEX (ix_transaction_table_name)"). \
                    order_by(asc(Transaction.id)). \
                    limit(self.chunk_size). \
                    options(joinedload(Transaction.namespace)).all()

                # index up to chunk_size transactions
                should_sleep = False
                if transactions:
                    self.index(transactions, db_session)
                    new_pointer = transactions[-1].id
                    self.update_pointer(new_pointer, db_session)
                    db_session.commit()
                else:
                    should_sleep = True
            if should_sleep:
                sleep(self.poll_interval)

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

        self.log.info('docs indexed', adds=len(add_docs),
                      deletes=len(delete_docs))

    def update_pointer(self, new_pointer, db_session):
        """
        Persist transaction pointer to support restarts, update
        self.transaction_pointer.

        """
        pointer = db_session.query(ContactSearchIndexCursor).first()
        if pointer is None:
            pointer = ContactSearchIndexCursor()
            db_session.add(pointer)
        pointer.transaction_id = new_pointer
        self.transaction_pointer = new_pointer
