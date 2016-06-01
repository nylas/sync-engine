from datetime import datetime

from inbox.api.kellogs import encode
from inbox.models import Transaction, ApiMessage, ApiThread
from inbox.models.mixins import HasRevisions
from inbox.models.util import transaction_objects


class ApiStore(object):

    def __init__(self, session, logger):
        self.session = session
        self.log = logger

    def get(self, namespace_id, table, public_id):
        record = self.session.query(table).filter(
                table.namespace_id == namespace_id,
                table.public_id == public_id).one_or_none()
        if not record:
            raise KeyError('API store not populated for %s' % public_id)

        return record

    def all(self, namespace_id, table, limit, offset=0, in_=None, subject=None, thread_public_id=None):
        query = self.session.query(table)\
                .filter(table.namespace_id == namespace_id)
        if in_ is not None:
            query = query.filter(table.categories.like('%' + in_ + '%'))
        if subject is not None:
            query = query.filter(table.subject == subject)
        if thread_public_id is not None:
            if table == ApiThread:
                query = query.filter(table.public_id == thread_public_id)
            else:
                query = query.filter(table.thread_public_id == thread_public_id)

        records = query[offset:limit]

        for record in records:
            yield record

    def bulk_update(self, objs):
        if len(objs) < 1:
            raise ValueError("can't update zero objects")
        table = objs[0].API_STORE_TABLE

        def checked_params(obj):
            if obj.API_STORE_TABLE != table:
                raise ValueError("can't update mismatched objects (found %s and %s)"
                        % (table, obj.API_STORE_TABLE))
            return table.params_from_obj(obj)

        obj_params = map(checked_params, objs)

        self.session.bulk_insert_mappings(table, obj_params)

    def update_from_transaction(self, txn, session=None):
        table = transaction_objects()[txn.object_type]

        if not hasattr(table, 'namespace_id'):
            return

        if txn.command == 'insert' or txn.command == 'update':
            record = None
            if session is not None:
                records = filter(lambda obj: isinstance(obj, table) and obj.id == txn.record_id, session)
                assert len(records) <= 1
                if len(records) == 1:
                    record = records[0]
            else:
                record = self.session.query(table).filter(
                        table.namespace_id == txn.namespace_id,
                        table.id == txn.record_id).one_or_none()
            if record is None:
                self.log.warning('ApiStore: %s transaction with missing %s %d (public_id %s)'
                        % (txn.command, txn.object_type, txn.record_id, txn.object_public_id))
                return

            self._update_object(record)
        elif txn.command == 'delete':
            self._clear_from_transaction(txn)
        else:
            raise ValueError('unexpected transaction command %s', txn.command)

        self.log.info('Updated ApiStore: %s for %s %d (public_id %s)'
            % (txn.command, txn.object_type, txn.record_id, txn.object_public_id))

    def _update_object(self, obj):
        if not hasattr(obj, 'API_STORE_TABLE'):
            self.log.warn('ApiStore: skipping update for %s' % type(obj))
            return

        table = obj.API_STORE_TABLE

        api_obj = table.from_obj(obj)

        api_obj = self.session.merge(api_obj)

    def _clear_from_transaction(self, txn):
        table = ApiMessage # TODO thread?

        self.session.query(table).filter(table.id == txn.record_id, table.namespace_id == txn.namespace_id).delete(synchronize_session=False)


def _new_transactions(session):
    for obj in session.new:
        if isinstance(obj, Transaction):
            yield obj

def write_to_api_store(store, session=None, transactions=None):
    if session is None and transactions is None:
        raise ValueError('need a session or some transactions to write to API store')
    elif transactions is not None:
        for txn in transactions:
            store.update_from_transaction(txn, session=session)
    else:
        for txn in _new_transactions(session):
            store.update_from_transaction(txn)
