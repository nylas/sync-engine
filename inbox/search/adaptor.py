import copy
import functools

import elasticsearch
from elasticsearch.helpers import bulk

from inbox.config import config
from inbox.log import get_logger
log = get_logger()
from inbox.search.query import DSLQueryEngine, MessageQuery, ThreadQuery
from inbox.search.mappings import NAMESPACE_INDEX_MAPPING

# Uncomment to enable logging of exactly which queries are made against the
# elasticsearch server, which you can paste directly into curl... also logs
# results, which is VERY verbose.
# import logging
# es_tracer = logging.getLogger('elasticsearch.trace')
# es_tracer.propagate = True

# Uncomment to disable verbose elasticsearch module logging.
# import logging
# es_logger = logging.getLogger('elasticsearch')
# es_logger.propagate = False


class SearchEngineError(Exception):
    """ Raised when connecting to the Elasticsearch server fails. """
    pass


def new_connection():
    """
    Get a new connection to the Elasticsearch server defined in the config.

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
        self.index_id = namespace_public_id

        # TODO(emfree): probably want to try to keep persistent connections
        # around, instead of creating a new one each time.
        self._connection = new_connection()
        self.log = log.new(component='search', index=namespace_public_id)

        self.create_index()

        self.messages = MessageSearchAdaptor(index_id=namespace_public_id,
                                             log=self.log)
        self.threads = ThreadSearchAdaptor(index_id=namespace_public_id,
                                           log=self.log)

    @wrap_es_errors
    def create_index(self):
        """
        Create an index for the namespace. If it already exists,
        re-configure it.

        """
        try:
            self.log.info('create_index')
            self._connection.indices.create(
                index=self.index_id,
                body={'mappings': NAMESPACE_INDEX_MAPPING})
        except elasticsearch.exceptions.RequestError:
            self.log.warning('create_index error, will re-configure.')
            # If the index already exists, ensure the right mappings are still
            # configured. Only works if action.auto_create_index = False.
            return self.configure_index()

    @wrap_es_errors
    def configure_index(self):
        """
        Configure the index for the namespace. In case of mapping conflicts,
        delete and re-create it.

        """
        try:
            self.log.info('configure_index')
            for doc_type, mapping in self.MAPPINGS.items():
                self._connection.indices.put_mapping(
                    index=self.index_id, doc_type=doc_type, body=mapping)
        except elasticsearch.exceptions.RequestError:
            self.log.warning('configure_index error, will delete + create.')
            self.delete_index()
            self.create_index()

    @wrap_es_errors
    def delete_index(self):
        """ Delete the index for the namespace. Obviously use with care. """
        self.log.info('delete_index')
        self._connection.indices.delete(index=[self.index_id])

    @wrap_es_errors
    def refresh_index(self):
        """
        Manually refresh the index for the namespace (happens periodically by
        default). Makes all operations performed since the last refresh
        available for search.

        """
        self.log.info('refresh_index')
        self._connection.indices.refresh(index=[self.index_id])


class BaseSearchAdaptor(object):
    """
    Base adaptor between the Nilas API and Elasticsearch for a single index and
    document type. Subclasses implement the document type specific logic.

    """
    def __init__(self, index_id, doc_type, query_class, log):
        self.index_id = index_id
        self.doc_type = doc_type
        self.query_engine = DSLQueryEngine(query_class)

        self.log = log

        # TODO(emfree): probably want to try to keep persistent connections
        # around, instead of creating a new one each time.
        self._connection = new_connection()

    @wrap_es_errors
    def _index_document(self, object_repr, **kwargs):
        """
        (Re)index a document for the object with Nilas API representation
        `object_repr`.

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
        except elasticsearch.exceptions.TransportError as e:
            self.log.error('Index failure', error=e.error,
                           doc_type=self.doc_type, object_id=index_args['_id'])
            raise

    @wrap_es_errors
    def _bulk(self, objects, parent=None):
        """
        Perform a batch of index operations rather than a single one.

        Arguments
        ---------
        objects:
            list of (op_type, object) tuples.

            op_type defines the index operation to perform
            ('index' for creates, updates and 'delete' for deletes)

            object is a dict of document attributes required for the operation.

        Returns
        -------
        Count of index operations on success, raises SearchEngineError on
        failure.

        """
        index_args = []

        def raise_error(failure):
            for op_type, info in failure.iteritems():
                if info.get('status') not in [None, 404]:
                    return True
            return False

        for op, object_repr in objects:
            args = dict(_op_type=op,
                        _index=self.index_id,
                        _type=self.doc_type,
                        _id=object_repr['id'])

            if op != 'delete':
                args.update(dict(_source=object_repr))

                if parent is not None:
                    args.update(dict(_parent=object_repr[parent]))

            index_args.append(args)

        try:
            count, failures = bulk(self._connection, index_args)
        except elasticsearch.exceptions.TransportError as e:
            self.log.error('Bulk index failure', error=e.error,
                           doc_type=self.doc_type,
                           object_ids=[i['_id'] for i in index_args])
            raise SearchEngineError('Bulk index failure!')
        if count != len(objects):
            self.log.error('Bulk index failure',
                           error='Not all indices created',
                           doc_type=self.doc_type,
                           object_ids=[i['_id'] for i in index_args],
                           failures=failures)

            if any(raise_error(f) for f in failures):
                raise SearchEngineError('Bulk index failure!')

        return count

    @wrap_es_errors
    def search(self, query, sort, max_results=100, offset=0, explain=True):
        """ Perform a search and return the results. """
        dsl_query = self.query_engine.generate_query(query)

        self.log.debug('search query', query=query, dsl_query=dsl_query)

        search_kwargs = dict(index=self.index_id,
                             doc_type=self.doc_type,
                             body=dsl_query,
                             size=max_results,
                             from_=offset,
                             explain=explain)

        # Split this out to a Sort class with subclasses for
        # MessageSort/ThreadSort if we expand sorting to be more flexible.
        if sort != 'relevance':
            if self.doc_type == 'message':
                timestamp_field = 'date'
            if self.doc_type == 'thread':
                timestamp_field = 'last_message_timestamp'
            search_kwargs['sort'] = '{}:desc'.format(timestamp_field)

        raw_results = self._connection.search(**search_kwargs)

        self._log_query(query, raw_results)

        total, api_results = self.query_engine.process_results(raw_results)
        return dict(total=total, results=api_results)

    @wrap_es_errors
    def get_mapping(self):
        return self._connection.indices.get_mapping(index=self.index_id,
                                                    doc_type=self.doc_type)

    def _log_query(self, query, raw_results):
        """
        Log query and result info, stripping out actual result bodies but
        keeping ids and metadata.

        """
        log_results = copy.deepcopy(raw_results)
        for hit in log_results['hits']['hits']:
            del hit['_source']
        self.log.debug('search query results', query=query,
                       results=log_results)


class MessageSearchAdaptor(BaseSearchAdaptor):
    """ Adaptor for the 'message' document type. """
    def __init__(self, index_id, log):
        BaseSearchAdaptor.__init__(self, index_id=index_id, doc_type='message',
                                   query_class=MessageQuery, log=log)

    def index(self, object_repr):
        self._index_document(object_repr, parent=object_repr['thread_id'])

    def bulk_index(self, objects):
        return self._bulk(objects, parent='thread_id')


class ThreadSearchAdaptor(BaseSearchAdaptor):
    """ Adaptor for the 'thread' document type. """
    def __init__(self, index_id, log):
        BaseSearchAdaptor.__init__(self, index_id=index_id, doc_type='thread',
                                   query_class=ThreadQuery, log=log)

    def index(self, object_repr):
        self._index_document(object_repr)

    def bulk_index(self, objects):
        return self._bulk(objects)
