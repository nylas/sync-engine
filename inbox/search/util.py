import dateutil.parser

from inbox.search.adaptor import NamespaceSearchEngine
from inbox.models.session import session_scope
from inbox.models import Message, Thread, Namespace
from inbox.api.kellogs import encode


def es_format_address_list(addresses):
    if addresses is None:
        return []
    return [email for name, email in addresses]


def es_format_tags_list(tags):
    if tags is None:
        return []
    return [tag.name for tag in tags]


def index_namespaces(namespace_public_id, updated_since=None):
    """
    Create an Elasticsearch index for a namespace and index its threads and
    messages. If `namespace_public_id` is None, all namespaces are indexed.
    Else, the specified one is.

    """
    if namespace_public_id is not None:
        return index_namespace(namespace_public_id, updated_since)

    with session_scope() as db_session:
        namespaces = db_session.query(Namespace.public_id).all()

    count = 0
    for n, in namespaces:
        count += index_namespace(n, updated_since)

    return count


def index_namespace(namespace_public_id, updated_since=None):
    """
    Create an Elasticsearch index for a namespace and index its threads and
    messages.

    """
    if updated_since is not None:
        updated_since = dateutil.parser.parse(updated_since)

    indexed_count = 0
    for obj_type in (Message, Thread):
        with session_scope() as db_session:
            namespace = db_session.query(Namespace).filter(
                Namespace.public_id == namespace_public_id).one()

            search_engine = NamespaceSearchEngine(namespace_public_id)
            # TODO: paginate the query so that we don't run out of memory on
            # life-sized accounts.
            objects = db_session.query(obj_type).filter(
                obj_type.namespace_id == namespace.id)

            if updated_since is not None:
                objects = objects.filter(obj_type.updated_at > updated_since)

            for obj in objects.all():
                encoded_obj = encode(
                    obj, namespace_public_id=namespace_public_id,
                    format_address_fn=es_format_address_list,
                    format_tags_fn=es_format_tags_list)
                if obj_type == Message:
                    search_engine.messages.index(encoded_obj)
                elif obj_type == Thread:
                    search_engine.threads.index(encoded_obj)

                indexed_count += 1

    return indexed_count
