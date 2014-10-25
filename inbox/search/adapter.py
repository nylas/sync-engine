import copy
import functools
import elasticsearch
from inbox.config import config
from inbox.log import get_logger
log = get_logger()


class SearchInterfaceError(Exception):
    """Exception raised if an error occurs connecting to the Elasticsearch
    backend."""
    pass


def new_connection():
    """Get a new connection to the Elasticsearch hosts defined in config.
    """
    elasticsearch_hosts = config.get('ELASTICSEARCH_HOSTS')
    if not elasticsearch_hosts:
        raise SearchInterfaceError('No search hosts configured')
    return elasticsearch.Elasticsearch(hosts=elasticsearch_hosts)


def wrap_es_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except elasticsearch.TransportError as e:
            raise SearchInterfaceError(e)
    return wrapper


class NamespaceSearchEngine(object):
    """Interface for interacting with the search backend within the namespace
    with public id `namespace_public_id`."""
    def __init__(self, namespace_public_id):
        self.messages = MessageSearchAdapter(index_id=namespace_public_id)
        self.threads = ThreadSearchAdapter(index_id=namespace_public_id)


class BaseSearchAdapter(object):
    """Adapter between the API and an Elasticsearch backend, for a single index
    "and document type."""
    def __init__(self, index_id, doc_type):
        # TODO(emfree) probably want to try to keep persistent connections
        # around, instead of creating a new one each time.
        self._connection = new_connection()
        self.index_id = index_id
        self.doc_type = doc_type

    # Mappings we want to configure on all indices.
    MAPPINGS = {
        'message': {
            '_parent': {'type': 'thread'}
        }
    }

    @wrap_es_errors
    def configure_index(self):
        """Create and/or configure an index for the given namespace."""
        try:
            self._connection.indices.create(
                index=self.index_id,
                body={'mappings': self.MAPPINGS})
        except elasticsearch.exceptions.RequestError:
            # If the index already exists, ensure the right mappings are still
            # configured.
            for doc_type, mapping in self.MAPPINGS.items():
                self._connection.indices.put_mapping(
                    index=self.index_id, doc_type=doc_type, body=mapping)

    @wrap_es_errors
    def _index_document(self, object_repr, **kwargs):
        """(Re)index a document for the object with API representation
        `object_repr`. Creates the actual index for the namespace if it doesn't
        already exist."""
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
            # Create the index for this namespace if it doesn't already exist.
            # TODO(emfree): this check only works if
            # `action.auto_create_index: false` is configured!
            self.configure_index()
            self._connection.index(**index_args)

    @wrap_es_errors
    def search(self, query, max_results=100, offset=0):
        """Retrieve search results."""
        dsl_query = self._generate_dsl_query(query)
        raw_results = self._connection.search(
            index=self.index_id,
            doc_type=self.doc_type,
            body=dsl_query,
            size=max_results,
            from_=offset)
        self._log_query(query, raw_results)
        return self._transform_results(raw_results)

    def _generate_dsl_query(self, query):
        """Transform a search query as passed from the API into a dictionary
        representing the query in the Elasticsearch query DSL."""
        # TODO: properly generate a query for threads that also checks child
        # messages.
        # TODO: we want to construct much more refined queries here,
        # and score e.g. participant field matches more highly than body text
        # matches.
        return {'query': {'match': {'_all': query}}}

    def _transform_results(self, raw_results):
        """Extract the actual API representations from the raw results
        returned from Elasticsearch."""
        return [hit['_source'] for hit in raw_results['hits']['hits']]

    def _log_query(self, query, raw_results):
        """Log query and result info, stripping out actual result bodies but
        keeping ids and metadata."""
        log_results = copy.deepcopy(raw_results)
        for hit in log_results['hits']['hits']:
            del hit['_source']
        log.debug('search query results', query=query, results=log_results)


class MessageSearchAdapter(BaseSearchAdapter):
    def __init__(self, index_id):
        BaseSearchAdapter.__init__(self, index_id=index_id, doc_type='message')

    def index(self, object_repr):
        """(Re)index a message with API representation `object_repr`."""
        self._index_document(object_repr, parent=object_repr['thread_id'])


class ThreadSearchAdapter(BaseSearchAdapter):
    def __init__(self, index_id):
        BaseSearchAdapter.__init__(self, index_id=index_id, doc_type='thread')

    def index(self, object_repr):
        """(Re)index a thread with API representation `object_repr`."""
        self._index_document(object_repr)
