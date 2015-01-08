import requests
from sqlalchemy.sql.expression import func

from inbox.config import config
from inbox.models.session import session_scope
from inbox.models import Namespace, Thread, Message


class IndexException(Exception):
    def __init__(self, namespace_id, namespace_public_id, obj_type, public_id):
        self.namespace_id = namespace_id
        self.namespace_public_id = namespace_public_id
        self.obj_type = obj_type
        self.public_id = public_id

    def __str__(self):
        return 'Index error'


def verify_backfilled_index(namespace_id, created_before=None):
    """
    Verify that a backfilled namespace is correctly indexed into Elasticsearch.

    Elasticsearch is queried for the documents whose ids == the public_ids of
    the last thread, message that fits the `namespace_id`, `created_before`
    criteria specified. Raises an IndexException if the namespace_id was
    not indexed successfully.

    Note: This check is not accurate for verifying index creation via the
    search-index-service.

    """
    es_host = config.get_required('ELASTICSEARCH_HOSTS')[0]

    with session_scope() as db_session:
        namespace_public_id = db_session.query(
            Namespace.public_id).get(namespace_id)

        for obj_type in [Thread, Message]:
            filters = [obj_type.namespace_id == namespace_id]

            if created_before:
                filters.append(obj_type.created_at <= created_before)

            # Pick an object to query Elasticsearch for.
            # Note this is the last object, rather than the first, in
            # order for the check to be accurate -
            # we bulk_index in chunks; if any chunk fails, an exception is
            # raised causing subsequent chunks to not be indexed.
            id_, _ = db_session.query(func.max(obj_type.id)).filter(
                *filters).one()
            public_id = db_session.query(obj_type.public_id).get(id_)

            # Query Elasticsearch.
            url = 'http://{}:{}/{}/{}/_count?q=id:{}'.format(
                es_host['host'], es_host['port'], namespace_public_id,
                obj_type.__tablename__, public_id)

            response = requests.get(url)

            if response.status_code != 200 or response.json()['count'] != 1:
                raise IndexException(namespace_id, namespace_public_id,
                                     obj_type.__tablename__, public_id)
