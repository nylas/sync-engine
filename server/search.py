import os
import logging as log

import xapian

from server.models import db_session, MessageMeta
from server.util import mkdirp

from sqlalchemy.orm import joinedload

from HTMLParser import HTMLParser

class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

INDEX_BASEPATH = os.path.join("cache", "index")

def db_path_for(user_id):
    return os.path.join(INDEX_BASEPATH, unicode(user_id))

def gen_search_index(user):
    log.info("Generating search index for {0}".format(user.g_email))
    dbpath = db_path_for(user.id)
    mkdirp(dbpath)
    database = xapian.WritableDatabase(dbpath, xapian.DB_CREATE_OR_OPEN)

    indexer = xapian.TermGenerator()
    stemmer = xapian.Stem("english")
    indexer.set_stemmer(stemmer)

    last_docid = database.get_lastdocid()
    msg_query = db_session.query(MessageMeta).filter(
            MessageMeta.user_id == user.id,
            MessageMeta.id > last_docid).options(joinedload('parts'))
    log.info("Have {0} messages to process".format(msg_query.count()))

    # for each message part, create unprocessed documents with date/subject/to/from
    # metadata and the plaintext part, and then process them!
    for msg in msg_query:
        plain_parts = [part for part in msg.parts \
                if part._content_type_common == 'text/plain']
        html_parts = [part for part in msg.parts \
                if part._content_type_common == 'text/html']
        log.info("{0}: {1} text/plain, {2} text/html".format(
                msg.g_msgid, len(plain_parts), len(html_parts)))
        # XXX do we really always want the first part only?
        text = None
        if plain_parts:
            text = plain_parts[0].get_data()
        elif html_parts:
            text = strip_tags(html_parts[0].get_data())

        # XXX also index attachments (add a 'type' field or something to
        # differentiate)

        if text is not None:
            doc = xapian.Document()
            doc.set_data(text)

            # XXX add to, cc, bcc, subject, date (perhaps weight more than
            # fulltext?)

            indexer.set_document(doc)
            indexer.index_text(text)
            database.replace_document(msg.id, doc)

    indexed_msgs = set([k for k in database.metadata_keys()])
    msgs =  set([id for id, in db_session.query(MessageMeta.id).filter_by(
            g_email=user.g_email).all()])
    to_delete = indexed_msgs.difference(msgs)
    log.info("{0} documents to remove...".format(len(to_delete)))

    for msg_id in to_delete:
        database.delete_document(msg_id)

    database.close()
    log.info("done.")

class SearchService:
    """ ZeroRPC interface to searching. """
    def search(self, user_id, query_string, limit=10):
        """ returns [(messagemeta.id, relevancerank), ...]

            fulltext is fulltext of the matching *part*, not the entire
            message.
        """
        # Treat all searches like wildcard searches unless the wildcard is
        # used elsewhere.
        # XXX we might also want to let queries _start_ with a * and still
        # append a * to the end
        if '*' not in query_string:
            query_string += '*'
        log.info("query '{0}' for user '{1}'".format(query_string, user_id))
        # Open the database for searching.
        database = xapian.Database(db_path_for(user_id))

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

        results = [(m.docid, m.rank) for m in matches]

        # Clean up.
        database.close()

        return results
