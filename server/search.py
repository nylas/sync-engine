import logging as log
import xapian

class SearchService:
    """ ZeroRPC interface to searching. """
    def search(user_email_address, query_string):
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
        print "Parsed query is: %s" % str(query)

        # Find the top 10 results for the query.
        enquire.set_query(query)
        matches = enquire.get_mset(0, 10)

        # Display the results.
        print "%i results found." % matches.get_matches_estimated()
        print "Results 1-%i:" % matches.size()

        # for m in matches:
        #     print "%i: %i%% docid=%i [%s]" % (m.rank + 1, m.percent, m.docid, m.document.get_data())
        # XXX what data structure to return?
        return matches
