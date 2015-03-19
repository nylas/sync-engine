class DSLQueryEngine(object):
    """
    Generate Elasticsearch DSL queries from API queries.
    Convert Elasticsearch query responses to API responses.

    """

    def __init__(self, query_class):
        self.query_class = query_class

    def generate_query(self, api_query):
        """
        Generate an Elasticsearch DSL query from the Inbox API search query.

        """

        if api_query is None:
            return self.query_class(api_query, '').match_all()

        assert isinstance(api_query, list)

        # Single and-query
        if len(api_query) == 1:
            assert isinstance(api_query[0], dict)
            return self.query_class(api_query[0], 'and').generate()

        # List of and-queries to be or-ed together
        return self.query_class(api_query, 'or').generate()

    def process_results(self, es_results):
        """
        Extract the Inbox API search results from the Elasticsearch results.

        """
        raw_results = es_results['hits']

        # Total number of hits
        total = raw_results['total']

        # Hits returned (#(hits) <= `size` passed in the request)
        results = []
        for h in raw_results['hits']:
            r = dict(relevance=h['_score'],
                     object=h['_source'])

            results.append(r)

        return total, results


class Query(object):
    # TODO[k]: Document more here
    """ Representation of an Elasticsearch DSL query. """

    NESTED_FIELD_FORMAT = '{}.{}'

    def __init__(self, query, query_type='and'):
        self.query = query
        self.query_type = query_type

    def convert(self):
        query_dict = self.convert_and() if self.query_type == 'and' else \
            self.convert_or()
        return dict(query={'bool': query_dict})

    def convert_or(self):
        #d_list = [self.__class__(q) for q in self.query]

        # TODO[k]: DO SOMETHING WITH d_list!
        # return d_list
        raise NotImplementedError

    def convert_and(self):
        must_list = []
        for field in self.query.iterkeys():
            if field == 'all':
                d = self.multi_match(field, boost=True)
            else:
                d = self.match(field)

            must_list.append(d)
        return dict(must=must_list)

    def _field_dict(self, field, value):
        # TODO[k]: check works as expected with non-string values
        if isinstance(value, list):
            field_dict = {field: dict(query=' '.join(v for v in value),
                          lenient=True)}
        else:
            field_dict = {field: dict(query=value, type='phrase',
                          lenient=True)}

        return field_dict

    def match(self, field):
        value = self.query[field]

        # Can _match directly
        if field not in self.nested_fields:
            return self._match(field, value)

        # _match each sub-field for nested fields
        sub_fields = self.nested_fields[field]

        should_list = [self._match(self.NESTED_FIELD_FORMAT.format(field, s),
                                   value) for s in sub_fields]

        query_dict = {'bool': dict(should=should_list)}
        nested_dict = {
            'path': field,
            'score_mode': 'avg',
            'query': query_dict
        }

        return dict(nested=nested_dict)

    def _match(self, field, value):
        """ Generate an Elasticsearch match or match_phrase query. """
        field_dict = self._field_dict(field, value)
        return dict(match=field_dict)

    def multi_match(self, field, boost=True):
        """
        Generate an Elasticsearch multi_match query.
        Simple matches and phrase matches are supported.

        Boosting is applied by default, set boost=False to score all field
        matches equally.

        """
        assert field == 'all' and self._fields
        value = self.query[field]

        if boost:
            return self._boosted_multi_match(field, value)
        else:
            return self._simple_multi_match(field, value)

    def _simple_multi_match(self, field, value):
        d = dict(fields=self._fields.keys())

        field_dict = self._field_dict(field, value)
        d.update(field_dict[field])
        d['type'] = 'most_fields'

        return dict(multi_match=d)

    def _boosted_multi_match(self, field, value):
        boosted_fields = []
        for f in self._fields:
            multiplier = self._fields.get(f)
            if multiplier:
                boosted_fields.append('{}^{}'.format(f, multiplier))
            else:
                boosted_fields.append(f)

        d = dict(fields=boosted_fields)

        field_dict = self._field_dict(field, value)
        d.update(field_dict[field])
        d['type'] = 'most_fields'

        return dict(multi_match=d)

    def match_all(self):
        return dict(query={'match_all': {}})

    def generate(self):
        raise NotImplementedError


class MessageQuery(Query):
    nested_fields = {
        'from': ['email', 'name'],
        'to': ['email', 'name'],
        'cc': ['email', 'name'],
        'bcc': ['email', 'name'],
        'files': ['size', 'id', 'content_type', 'filename']
    }

    def __init__(self, query, query_type='and'):
        # TODO[k]: files have content_type, size, filename, id.
        # We exclude the namespace_id.
        attrs = ['id', 'object', 'subject', 'from', 'to', 'cc', 'bcc', 'date',
                 'thread_id', 'snippet', 'body', 'unread', 'files', 'version',
                 'state']
        self._fields = dict((k, None) for k in attrs)

        Query.__init__(self, query, query_type)

        self.apply_weights()

    def apply_weights(self):
        if not self.query or 'all' not in self.query:
            return

        # Arbitrarily assigned boost_score
        if 'weights' not in self.query:
            for f in ['subject', 'snippet', 'body']:
                self._fields[f] = 3
        else:
            self._fields.update(self.query['weights'])
            del self.query['weights']

    def generate(self):
        query_dict = self.convert()

        # TODO[k]:
        # Fix for case self.query is a list i.e. OR-query
        # Fix to support cross Thread/Message field queries
        if self.query.keys()[0] in self._fields or \
                self.query.keys()[0] == 'all':
            return query_dict

        query_dict.update(dict(type='thread'))
        return {'query': dict(has_parent=query_dict)}


class ThreadQuery(Query):
    nested_fields = {
        'tags': ['id', 'name'],
        'participants': ['email', 'name']
    }

    def __init__(self, query, query_type='and'):
        # TODO[k]: tags have name, id.
        # We exclude the namespace_id.
        attrs = ['id', 'object', 'subject', 'participants', 'tags',
                 'last_message_timestamp', 'first_message_timestamp']
        self._fields = dict((k, None) for k in attrs)

        Query.__init__(self, query, query_type)

        self.apply_weights()

    def apply_weights(self):
        if not self.query or 'all' not in self.query:
            return

        # Arbitrarily assigned boost_score
        if 'weights' not in self.query:
            for f in ['subject', 'snippet', 'participants', 'tags']:
                self._fields[f] = 3
        else:
            self._fields.update(self.query['weights'])
            del self.query['weights']

    def generate(self, min_children=1):
        query_dict = self.convert()

        # TODO[k]:
        # Fix for case self.query is a list i.e. OR-query
        # Fix to support cross Thread/Message field queries
        if self.query.keys()[0] in self._fields or \
                self.query.keys()[0] == 'all':
            return query_dict

        query_dict.update(dict(type='message',
                               min_children=min_children))
        return {'query': dict(has_child=query_dict)}
