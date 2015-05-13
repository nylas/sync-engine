import dateutil.parser

import gevent
from sqlalchemy.orm import joinedload, subqueryload

from inbox.log import get_logger
log = get_logger()
from inbox.models.session import session_scope
from inbox.models import Namespace, Thread, Message
from inbox.api.kellogs import encode
from inbox.search.adaptor import NamespaceSearchEngine
from inbox.sqlalchemy_ext.util import safer_yield_per

CHUNK_SIZE = 500


def index_namespaces(namespace_ids=None, created_before=None):
    """
    Create an Elasticsearch index for each namespace in the `namespace_ids`
    list (specified by id), and index its threads and messages.
    If `namespace_ids` is None, all namespaces are indexed.

    """
    pool = []

    with session_scope() as db_session:
        q = db_session.query(Namespace.id, Namespace.public_id)

        if namespace_ids is not None:
            namespaces = q.filter(Namespace.id.in_(namespace_ids)).all()
        else:
            namespaces = q.all()

    for (id_, public_id) in namespaces:
        pool.append(gevent.spawn(index_threads, id_, public_id,
                                 created_before))
        pool.append(gevent.spawn(index_messages, id_, public_id,
                                 created_before))

    gevent.joinall(pool)

    return sum([g.value for g in pool])


def delete_namespace_indexes(namespace_ids):
    """
    Delete the Elasticsearch indexes for the namespaces in the `namespace_ids`
    list.

    """
    pool = []

    with session_scope() as db_session:
        q = db_session.query(Namespace.id, Namespace.public_id)

        if namespace_ids is not None:
            namespaces = q.filter(Namespace.id.in_(namespace_ids)).all()
        else:
            namespaces = q.all()

    for (id_, public_id) in namespaces:
        pool.append(gevent.spawn(delete_index, id_, public_id))

    gevent.joinall(pool)


def index_threads(namespace_id, namespace_public_id, created_before=None):
    """ Index the threads of a namespace. """
    if created_before is not None:
        created_before = dateutil.parser.parse(created_before)

    indexed_count = 0
    search_engine = NamespaceSearchEngine(namespace_public_id,
                                          create_index=True)

    with session_scope() as db_session:
        query = db_session.query(Thread).filter(
            Thread.namespace_id == namespace_id)

        if created_before is not None:
            query = query.filter(Thread.created_at <= created_before)

        query = query.options(
            subqueryload(Thread.messages).
            load_only('public_id', 'is_draft', 'from_addr', 'to_addr',
                      'cc_addr', 'bcc_addr'),
            subqueryload('tagitems').joinedload('tag').
            load_only('public_id', 'name'))

        encoded = []
        for obj in safer_yield_per(query, Thread.id, 0, CHUNK_SIZE):
            index_obj = encode(obj, namespace_public_id=namespace_public_id)
            encoded.append(('index', index_obj))

    log.info('Going to index threads', namespace_id=namespace_id,
             namespace_public_id=namespace_public_id)

    indexed_count += search_engine.threads.bulk_index(encoded)

    log.info('Indexed threads', namespace_id=namespace_id,
             namespace_public_id=namespace_public_id,
             thread_count=indexed_count)

    return indexed_count


def index_messages(namespace_id, namespace_public_id, created_before=None):
    """ Index the messages of a namespace. """
    if created_before is not None:
        created_before = dateutil.parser.parse(created_before)

    indexed_count = 0
    search_engine = NamespaceSearchEngine(namespace_public_id,
                                          create_index=True)

    with session_scope() as db_session:
        query = db_session.query(Message).filter(
            Message.namespace_id == namespace_id)

        if created_before is not None:
            query = query.filter(Message.created_at <= created_before)

        query = query.options(joinedload(Message.parts).
                              load_only('content_disposition'))

        encoded = []
        for obj in safer_yield_per(query, Message.id, 0, CHUNK_SIZE):
            index_obj = encode(obj, namespace_public_id=namespace_public_id)
            encoded.append(('index', index_obj))

    log.info('Going to index messages', namespace_id=namespace_id,
             namespace_public_id=namespace_public_id)

    indexed_count += search_engine.messages.bulk_index(encoded)

    log.info('Indexed messages', namespace_id=namespace_id,
             namespace_public_id=namespace_public_id,
             message_count=indexed_count)

    return indexed_count


def delete_index(namespace_id, namespace_public_id):
    """
    Delete a namespace index.
    USE WITH CAUTION.

    """
    search_engine = NamespaceSearchEngine(namespace_public_id)

    # TODO[k]: Error handling
    search_engine.delete_index()

    log.info('Deleted namespace index', namespace_id=namespace_id,
             namespace_public_id=namespace_public_id)
