from datetime import datetime

from sqlalchemy.sql import text

from inbox.api.kellogs import encode
from inbox.models import Transaction, ApiMessage, ApiThread
from inbox.models.mixins import HasRevisions
from inbox.models.util import transaction_objects


class ApiStore(object):

    def __init__(self, session, logger):
        self.session = session
        self.log = logger

    def get_with_patch(self, namespace_id, table, public_id):
        patch = self.get_patch(namespace_id, table, public_id)
        if patch:
            return patch

        record = self.get(namespace_id, table, public_id)
        if not record:
            raise KeyError('table %s not populated for public_id %s'
                    % (table.__tablename__, public_id))

        return record

    def get(self, namespace_id, table, public_id):
        record = self.session.query(table).filter(
                table.namespace_id == namespace_id,
                table.public_id == public_id).one_or_none()

        return record

    def get_patch(self, namespace_id, table, public_id):
        if hasattr(table, 'PATCH_TABLE'):
            return self.get(namespace_id, table.PATCH_TABLE, public_id)

    def get_patches(self, namespace_id, table, public_ids):
        if hasattr(table, 'PATCH_TABLE'):
            return self.session.query(table.PATCH_TABLE).filter(
                    table.namespace_id == namespace_id,
                    table.public_id.in_(public_ids)).all()
        else:
            return []

    def messages(self, namespace_id, view, limit, offset=0, in_=None, subject=None, thread_public_id=None, from_addr=None, to_addr=None, cc_addr=None, bcc_addr=None):
        query = self.session.query(ApiMessage)\
                .filter(ApiMessage.namespace_id == namespace_id)
        if in_ is not None:
            query = _filter_json_column(query, ApiMessage.categories, in_)
        if subject is not None:
            query = query.filter(ApiMessage.subject == subject)
        if thread_public_id is not None:
            query = query.filter(ApiMessage.thread_public_id == thread_public_id)
        if from_addr is not None:
            query = _filter_json_column(query, ApiMessage.from_addr, from_addr)
        if to_addr is not None:
            query = _filter_json_column(query, ApiMessage.to_addr, to_addr)
        if cc_addr is not None:
            query = _filter_json_column(query, ApiMessage.cc_addr, cc_addr)
        if bcc_addr is not None:
            query = _filter_json_column(query, ApiMessage.bcc_addr, bcc_addr)

        return self._records_with_patches(view, query, namespace_id, ApiMessage, offset, limit)

    def threads(self, namespace_id, view, limit, offset=0, in_=None, subject=None, public_id=None, from_addr=None, to_addr=None, cc_addr=None, bcc_addr=None):
        query = self.session.query(ApiThread)\
                .filter(ApiThread.namespace_id == namespace_id)
        if in_ is not None:
            query = _filter_json_column(query, ApiThread.categories, in_)
        if subject is not None:
            query = query.filter(ApiThread.subject == subject)
        if public_id is not None:
            query = query.filter(ApiThread.public_id == public_id)
        if from_addr is not None:
            query = _filter_json_column(query, ApiThread.from_addrs, from_addr)
        if to_addr is not None:
            query = _filter_json_column(query, ApiThread.to_addrs, to_addr)
        if cc_addr is not None:
            query = _filter_json_column(query, ApiThread.cc_addrs, cc_addr)
        if bcc_addr is not None:
            query = _filter_json_column(query, ApiThread.bcc_addrs, bcc_addr)

        return self._records_with_patches(view, query, namespace_id, ApiThread, offset, limit)

    def _records_with_patches(self, view, query, namespace_id, table, offset, limit):
        if view == 'count':
            if offset != 0:
                raise ValueError("Can't combine view=count with offset")
            return query.count()

        records = query\
                .order_by(table.api_ordering)\
                [offset:offset+limit]

        patches = self.get_patches(namespace_id, table, [r.public_id for r in records])
        patches_by_id = {}
        for patch in patches:
            patches_by_id[patch.id] = patch

        def patched(record):
            if record.id in patches_by_id:
                return patches_by_id[record.id]
            else:
                return record
        return map(patched, records)

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

    def patch(self, obj):
        table = _patch_table_for(obj)
        if not table:
            self.log.warn('ApiStore: skipping patch for %s' % type(obj))
            return

        patch = table.from_obj(obj)

        # TODO think about concurrent patches
        self.session.add(patch)

        self.log.info('Patched ApiStore: %s %d (public_id %s)'
            % (obj.API_OBJECT_NAME, obj.id, obj.public_id))

    def unpatch(self, namespace_id, table_name, record_id, status):
        table = transaction_objects()[table_name]
        patch_table = _patch_table_for(table)
        if not patch_table:
            self.log.warn('ApiStore: skipping unpatch for %s' % table)
            return

        # TODO think about multiple patches
        self.session.query(patch_table).filter(patch_table.id == record_id, patch_table.namespace_id == namespace_id).delete(synchronize_session=False)

        self.log.info('Unpatched ApiStore: %s %d' % (table_name, record_id))

    def _clear_from_transaction(self, txn):
        table = ApiMessage # TODO thread?

        self.session.query(table).filter(table.id == txn.record_id, table.namespace_id == txn.namespace_id).delete(synchronize_session=False)

def _patch_table_for(table_or_obj):
    if hasattr(table_or_obj, 'API_STORE_TABLE') and hasattr(table_or_obj.API_STORE_TABLE, 'PATCH_TABLE'):
        return table_or_obj.API_STORE_TABLE.PATCH_TABLE

# TODO not a correct or efficient way of doing this query
def _filter_json_column(query, column, search):
    like_expr = text("'%' :search '%'").bindparams(search=search)
    return query.filter(column != [], column.like(like_expr))



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
