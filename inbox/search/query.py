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
    """ Representation of an Elasticsearch DSL query.

        Converts a simple field query e.g. {"from": "foobar@gmail.com"}
        into the appropriate DSL, including expanding nested fields into
        a 'nested' query. Supports query_type 'and' or 'or'.

        When subclassing, define:
           nested_fields: {field: [subfield]} - which fields to expand
           _fields: {field: score} dictionary of fields we want to search,
                    including nested parent fields (e.g. 'name'). These nested
                    fields should have their children defined in nested_fields.
                    score: can be None if not boosting that field (default).

        Generates two types of query:
           match: simple match query against a specific field
           multi_match: simple or boosted multi-match query covering all fields

        If there are nested fields present, the base convert() method will
        return a boolean 'should' query which also explicitly searches those
        fields, since the ElasticSearch multi_match operator does not.
    """

    NESTED_FIELD_FORMAT = '{}.{}'

    def __init__(self, query, query_type='and'):
        """ Initialize the query.

            query: dict or list of dicts in {fieldname: value} format.

            query_type: how to treat individual fieldname: value matches.
                        'and': all terms present in value must appear in field
                        'or': at least one term must appear in field
        """
        self.query = query

        if isinstance(self.query, list):
            # Supplying a list of queries means "OR" them.
            self.query_type = 'or'
        else:
            self.query_type = query_type

    def convert(self):
        query_dict = self.convert_query()
        return dict(query={'bool': query_dict})

    def convert_query(self):
        query_list = self.generate_sub_queries()
        # We are using a 'should' for 'all' queries, because the query should
        # appear in one of the sub queries, i.e either the nested queries or
        # the multi_match.
        key = 'should' if self.query_type == 'or' else 'must'
        return {key: query_list}

    def generate_sub_queries(self):
        # Generates a list of individual match and multi_match queries
        # satisfying the search specified in self.query.
        query_list = []
        if isinstance(self.query, list):
            # If we have a list of queries, we create a list containing the
            # expanded form of each one, which will be 'OR'd together.
            # NOTE: This is not completely comprehensive, in that it does not
            # work well if one of the "or"-d queries is an "all" query. This
            # case is currently rejected in validation.
            for q in self.query:
                query_constructor = self.__class__(q)
                query_clause = query_constructor.generate_sub_queries()
                query_list.extend(query_clause)
        else:
            # If we have a single query, we match it. Note that an "all" query
            # will potentially give us a list of queries back.
            for field in self.query.iterkeys():
                value = self.query[field]
                if field == 'all':
                    match_queries = self.match_all_fields(value)
                    query_list.extend(match_queries)
                else:
                    d = self.match(field, value)
                    query_list.append(d)
        return query_list

    def _construct_query(self, value, boost_score=None):
        """Constructs a query dictionary for the value supplied.
           value: must be a scalar value (eg. string).

           Uses operator 'and' or 'or' depending on the query_type set; this is
           'and' by default, 'or' for "all"-field queries.
        """
        combine_operator = self.query_type
        query_dict = dict(query=value, operator=combine_operator,
                          lenient=True)
        if boost_score:
            query_dict['boost'] = boost_score
        return query_dict

    def match(self, field, value, boost_score=None):
        """Constructs a match query for the supplied field and value.
           If the supplied field is the parent of a nested type, e.g. 'from',
           we generate subqueries across the child fields and construct the
           approporiate 'nested' query.
           boost_score: boosting value for the queried field (can be None).
        """

        # Not a nested field? Call _match directly
        if field not in self.nested_fields:
            return self._match(field, value)

        # Otherwise, field is a nested field and has sub-fields.
        # We call _match for each sub-field to generate a composite query,
        # e.g 'from' becomes queries for 'from.name' and 'from.email'.
        sub_fields = self.nested_fields[field]

        # Generate the fully qualified name for each field (eg. 'from.name')
        full_fields = [self.NESTED_FIELD_FORMAT.format(field, sub)
                       for sub in sub_fields]

        # Pass along the boosting score into the individual queries;
        # the caret syntax only applies inside multi_match.
        should_list = [self._match(f, value, boost_score) for f in full_fields]

        query_dict = {'bool': dict(should=should_list)}
        nested_dict = {
            'path': field,
            'score_mode': 'avg',
            'query': query_dict
        }

        return dict(nested=nested_dict)

    def match_all_fields(self, value):
        """Generate a composite query for "all" matches that combines a
           multi-match query with individual queries for nested fields.
        """
        query_list = []
        # Multi match on non-nested fields
        multi = self.multi_match(value, boosted=True)
        query_list.append(multi)
        # Add nested queries for nested fields, providing
        # the boosting score from the parent field.
        for f in self.nested_fields:
            boost_score = self._fields.get(f)
            d = self.match(f, self.query['all'], boost_score=boost_score)
            query_list.append(d)
        return query_list

    def _match(self, field, value, boost_score=None):
        """ Generate an Elasticsearch match or match_phrase query. """
        query_dict = self._construct_query(value, boost_score=boost_score)
        field_dict = {field: query_dict}
        return dict(match=field_dict)

    def _boost(self, field):
        """ Rewrites a field name with caret-boosted syntax if that field
            has a boosting score set in self._fields[field].
            e.g. 'subject' becomes 'subject^3' if self._fields['subject'] = 3.
        """
        multiplier = self._fields.get(field)
        if multiplier:
            return '{}^{}'.format(field, multiplier)
        return field

    def multi_match(self, value, boosted=True):
        """Generate an Elasticsearch multi_match query.
           Boosting is applied by default; set boost=False to score all field
           matches equally.

           Default to "OR" type matching, since otherwise ES requires that
           every token appear in the same field to consider it a match.
        """
        self.query_type = 'or'

        multi_fields = list(set(self._fields.keys()) - set(self.nested_fields))

        if boosted:
            # Rewrite the field names in boosted format, if applicable
            multi_fields = [self._boost(f) for f in multi_fields]

        d = dict(fields=multi_fields)

        query_dict = self._construct_query(value)
        d.update(query_dict)
        d['type'] = 'most_fields'

        return dict(multi_match=d)

    def queried_fields(self):
        """ Returns a list of all the fields this query explicitly specifies.
        """
        fields = []
        if isinstance(self.query, list):
            for subquery in self.query:
                fields.extend(subquery.keys())
        else:
            fields = self.query.keys()
        return list(set(fields))

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
        'files': ['content_type', 'filename']
    }
    attrs = ['id', 'object', 'subject', 'from', 'to', 'cc', 'bcc', 'date',
             'thread_id', 'snippet', 'body', 'unread', 'files', 'state']

    def __init__(self, query, query_type='and'):
        self._fields = dict((k, None) for k in self.attrs)
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

    def generate_all(self):
        return self.convert()

    def generate_parent_query(self, query, query_type):
        # Regenerate the parent query so we capture nested fields
        thr_query = ThreadQuery(query=query, query_type=query_type)
        query_dict = thr_query.convert()

        query_dict.update(dict(type='thread'))
        return dict(has_parent=query_dict)

    def generate(self):
        queried_fields = self.queried_fields()
        foreign_fields = set(queried_fields) - set(self.attrs)
        native_fields = set(queried_fields) - foreign_fields

        if foreign_fields == set():
            # We are only querying message properties
            return self.convert()

        if foreign_fields == set(['all']):
            return self.generate_all()

        if foreign_fields - set(['all']) != foreign_fields:
            # We don't support a mix of parent fields and 'all' yet.
            raise NotImplementedError("Cannot mix all and thread fields")

        if len(native_fields) != 0:
            # We don't support a mix of parent and child fields yet.
            raise NotImplementedError("Cannot mix message and thread fields")

        # Otherwise, we're just querying parent fields
        parent_dict = self.generate_parent_query(self.query, self.query_type)
        return {'query': parent_dict}


class ThreadQuery(Query):
    nested_fields = {
        'tags': ['name'],
        'participants': ['email', 'name']
    }

    attrs = ['id', 'object', 'subject', 'participants',
             'tags', 'last_message_timestamp', 'first_message_timestamp']
    # Which child (message) attributes to include in an 'all' query
    child_attrs = ['body', 'files']
    # Minimum children that need to match for parent to match
    min_children = 1

    def __init__(self, query, query_type='and'):
        # We exclude the namespace_id.

        self._fields = dict((k, None) for k in self.attrs)

        Query.__init__(self, query, query_type)

        self.apply_weights()

    def apply_weights(self):
        if not self.query or 'all' not in self.query:
            return

        # Arbitrarily assigned boost_score
        if 'weights' not in self.query:
            for f in ['subject', 'participants', 'tags']:
                self._fields[f] = 3
        else:
            self._fields.update(self.query['weights'])
            del self.query['weights']

    def generate_all(self):
        # Generate the sub queries, creating the 'all' query and
        # searching any other fields incluided in self.query
        should_list = self.generate_sub_queries()

        # We also include child documents whose files or body might
        # match the provided query, by appending has_child queries.
        value = self.query['all']

        for c in self.child_attrs:
            # Pass through the "or" lenience to ensure that we don't
            # *only* return results where the child matches.
            child_query = {c: value}
            child_dict = self.generate_child_query(child_query, 'or')
            should_list.append(child_dict)

        query_dict = dict(should=should_list)
        return {'query': {'bool': query_dict}}

    def generate_child_query(self, query, query_type):
        # Generate a has_child query to include child properties
        msg_query = MessageQuery(query=query, query_type=query_type)
        query_dict = msg_query.convert()
        query_dict.update(dict(type='message',
                               min_children=self.min_children))
        return dict(has_child=query_dict)

    def generate(self):
        queried_fields = self.queried_fields()
        foreign_fields = set(queried_fields) - set(self.attrs)
        native_fields = set(queried_fields) - foreign_fields

        if foreign_fields == set():
            # We are only querying thread fields
            return self.convert()

        if foreign_fields == set(['all']):
            return self.generate_all()

        if foreign_fields - set(['all']) != foreign_fields:
            # We don't support a mix of child fields and 'all' yet.
            raise NotImplementedError("Cannot mix all and message fields")

        if len(native_fields) != 0:
            # We don't support a mix of parent and child fields yet.
            raise NotImplementedError("Cannot mix thread and message fields")

        # We are *only* querying child fields
        child_dict = self.generate_child_query(self.query, self.query_type)
        return {'query': child_dict}
