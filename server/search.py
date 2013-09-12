import logging as log
import xapian

class SearchService:
    """ ZeroRPC interface to searching. """
    def search(self, user_email_address, query_string, limit=10):
        """ returns [(g_msgid, relevancerank, fulltext)] """
        # treat all searches like wildcard searches unless the wildcard is
        # used elsewhere
        # XXX we might also want to let queries _start_ with a * and still
        # append a * to the end
        if '*' not in query_string:
            query_string += '*'
        log.info("Searching for {0} on behalf of {1}".format(query_string,
            user_email_address))
        # Open the database for searching.
        database = xapian.Database("parts.db")

        # Start an enquire session.
        enquire = xapian.Enquire(database)

        # Parse the query string to produce a Xapian::Query object.
        qp = xapian.QueryParser()
        stemmer = xapian.Stem("english")
        qp.set_stemmer(stemmer)
        qp.set_database(database)
        qp.set_stemming_strategy(xapian.QueryParser.STEM_SOME)

        query = qp.parse_query(query_string, xapian.QueryParser.FLAG_WILDCARD)
        log.info("Parsed query is: %s" % str(query))

        # Find the top N results for the query.
        enquire.set_query(query)
        matches = enquire.get_mset(0, limit)

        # Display the results.
        log.info("%i results found." % matches.get_matches_estimated())
        log.info("Results 1-%i:" % matches.size())

        # XXX I think xapian also allows to apply highlights, can we do that?

        results = [(m.docid, m.rank, m.document.get_data()) for m in matches]
        return results
