import copy
import functools

import elasticsearch

from inbox.config import config
from inbox.log import get_logger
log = get_logger()
from inbox.search.query import DSLQueryEngine, MessageQuery, ThreadQuery
from inbox.search.mappings import NAMESPACE_INDEX_MAPPING


class SearchEngineError(Exception):
    """
    Exception raised if an error occurs connecting to the Elasticsearch
    backend.

    """
    pass


def new_connection():
    """
    Get a new connection to the Elasticsearch hosts defined in config.

    """
    elasticsearch_hosts = config.get('ELASTICSEARCH_HOSTS')
    if not elasticsearch_hosts:
        raise SearchEngineError('No search hosts configured')
    return elasticsearch.Elasticsearch(hosts=elasticsearch_hosts)


def wrap_es_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except elasticsearch.TransportError as e:
            raise SearchEngineError(e)
    return wrapper


class NamespaceSearchEngine(object):
    """
    Interface to create and interact with the Elasticsearch datastore
    (i.e. index) for a namespace, identified by the namespace public id.

    """
    MAPPINGS = NAMESPACE_INDEX_MAPPING

    def __init__(self, namespace_public_id):
        # TODO(emfree): probably want to try to keep persistent connections
        # around, instead of creating a new one each time.
        self.index_id = namespace_public_id

        self._connection = new_connection()
        self.create_index()

        self.messages = MessageSearchAdaptor(index_id=namespace_public_id)
        self.threads = ThreadSearchAdaptor(index_id=namespace_public_id)

    @wrap_es_errors
    def create_index(self):
        """
        Create an index for the given namespace.
        If it already exists, re-configure it.

        """
        try:
            self._connection.indices.create(
                index=self.index_id,
                body={'mappings': NAMESPACE_INDEX_MAPPING})
        except elasticsearch.exceptions.RequestError:
            # If the index already exists, ensure the right mappings are still
            # configured.
            # Only works if action.auto_create_index = False.
            return self.configure_index()

    @wrap_es_errors
    def configure_index(self):
        try:
            for doc_type, mapping in self.MAPPINGS.items():
                self._connection.indices.put_mapping(
                    index=self.index_id, doc_type=doc_type, body=mapping)
        except elasticsearch.exceptions.RequestError:
            self.delete_index()
            self.create_index()

    @wrap_es_errors
    def delete_index(self):
        self._connection.indices.delete(index=[self.index_id])


class BaseSearchAdaptor(object):
    """
    Adapter between the API and an Elasticsearch backend, for a single index
    and document type.

    """
    def __init__(self, index_id, doc_type, query_class):
        # TODO(emfree): probably want to try to keep persistent connections
        # around, instead of creating a new one each time.
        self._connection = new_connection()
        self.index_id = index_id
        self.doc_type = doc_type

        self.query_engine = DSLQueryEngine(query_class)

    @wrap_es_errors
    def _index_document(self, object_repr, **kwargs):
        """
        (Re)index a document for the object with API representation
        `object_repr`. Creates the actual index for the namespace if it doesn't
        already exist.

        """
        assert self.index_id == object_repr['namespace_id']

        index_args = dict(
            index=self.index_id,
            doc_type=self.doc_type,
            id=object_repr['id'],
            body=object_repr)
        index_args.update(**kwargs)
        try:
            self._connection.index(**index_args)
        except elasticsearch.exceptions.NotFoundError:
            raise

    @wrap_es_errors
    def search(self, query, max_results=100, offset=0, explain=True):
        """Perform a search and return the results."""
        dsl_query = self.query_engine.generate_query(query)

        log.debug('search query', query=query, dsl_query=dsl_query)

        raw_results = self._connection.search(
            index=self.index_id,
            doc_type=self.doc_type,
            body=dsl_query,
            size=max_results,
            from_=offset,
            explain=explain)

        self._log_query(query, raw_results)

        api_results = self.query_engine.process_results(raw_results)
        return api_results

    def _log_query(self, query, raw_results):
        """
        Log query and result info, stripping out actual result bodies but
        keeping ids and metadata.

        """
        log_results = copy.deepcopy(raw_results)
        for hit in log_results['hits']['hits']:
            del hit['_source']
        log.debug('search query results', query=query, results=log_results)

    @wrap_es_errors
    def get_mapping(self):
        return self._connection.indices.get_mapping(index=self.index_id,
                                                    doc_type=self.doc_type)


class MessageSearchAdaptor(BaseSearchAdaptor):
    def __init__(self, index_id):
        BaseSearchAdaptor.__init__(self, index_id=index_id, doc_type='message',
                                   query_class=MessageQuery)

    def index(self, object_repr):
        """(Re)index a message with API representation `object_repr`."""
        self._index_document(object_repr, parent=object_repr['thread_id'])


class ThreadSearchAdaptor(BaseSearchAdaptor):
    def __init__(self, index_id):
        BaseSearchAdaptor.__init__(self, index_id=index_id, doc_type='thread',
                                   query_class=ThreadQuery)

    def index(self, object_repr):
        """(Re)index a thread with API representation `object_repr`."""
        self._index_document(object_repr)
