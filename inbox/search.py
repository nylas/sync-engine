from __future__ import division
import os
from .log import get_logger
log = get_logger()

import xapian as x_

from inbox.models import session_scope
from inbox.models.tables.base import Message, Namespace
from inbox.util.file import mkdirp
from inbox.util.html import strip_tags

from sqlalchemy import distinct
from sqlalchemy.orm import joinedload

from calendar import timegm

INDEX_BASEPATH = os.path.join("cache", "index")

# see http://xapian.org/docs/queryparser.html "Partially entered query
# matching" and
# http://xapian.org/docs/apidoc/html/classXapian_1_1QueryParser.html
QUERY_FLAGS =  x_.QueryParser.FLAG_WILDCARD \
        | x_.QueryParser.FLAG_LOVEHATE | x_.QueryParser.FLAG_BOOLEAN \
        | x_.QueryParser.FLAG_SYNONYM \
        | x_.QueryParser.FLAG_SPELLING_CORRECTION \
        | x_.QueryParser.FLAG_PHRASE
        # XXX conflicts with spelling correction somehow
        # | x_.QueryParser.FLAG_PARTIAL

def db_path_for(namespace_id):
    return os.path.join(INDEX_BASEPATH, unicode(namespace_id))

def to_indexable(parsed_addr):
    """ Takes a parsed To/From/Cc/Bcc address and returns a string
        version for indexing.
    """
    addr = parsed_addr[1]
    # e.g. 'Christine Spang spang@inboxapp.com'
    name = parsed_addr[0] if parsed_addr[0] is not None else ''
    return ' '.join([name, addr])

def gen_search_index(db_session, namespace):
    log.info("Generating search index for namespace {0}".format(namespace.id))
    dbpath = db_path_for(namespace.id)
    mkdirp(dbpath)
    database = x_.WritableDatabase(dbpath, x_.DB_CREATE_OR_OPEN)

    indexer = x_.TermGenerator()
    stemmer = x_.Stem("english")
    indexer.set_stemmer(stemmer)
    indexer.set_database(database)
    indexer.set_flags(indexer.FLAG_SPELLING)

    last_docid = database.get_lastdocid()
    msg_query = db_session.query(Message).filter(
            Message.namespace_id == namespace.id,
            Message.id > last_docid).options(joinedload('parts')) \
                    .order_by(Message.id.desc())
    log.info("Have {0} messages to process".format(msg_query.count()))

    # for each message part, create unprocessed documents with date/subject/to/from
    # metadata and the plaintext part, and then process them!
    total = msg_query.count()
    done = 0
    for msg in msg_query.yield_per(1000):
        text = strip_tags(msg.sanitized_body)

        # XXX also index attachments (add a 'type' field or something to
        # differentiate)

        if text is not None:
            doc = x_.Document()
            doc.set_data(text)

            indexer.set_document(doc)

            # NOTE: the integer here is a multiplier on the term frequency
            # (used for calculating relevance). We add terms with and without
            # a field prefix, so documents are returned on a generic search
            # *and* when fields are specifically searched for, e.g. to:mg@mit.edu
            if msg.subject is not None:
                indexer.index_text(msg.subject, 10)
                indexer.index_text(msg.subject, 10, 'XSUBJECT')
            if msg.from_addr is not None:
                from_ = to_indexable(msg.from_addr)
                indexer.index_text(from_, 1)
                indexer.index_text(from_, 1, 'XFROM')
            if msg.to_addr is not None:
                to = ' '.join([to_indexable(parsed_addr) for parsed_addr in msg.to_addr])
                indexer.index_text(to, 5)
                indexer.index_text(to, 5, 'XTO')
            if msg.cc_addr is not None:
                cc = ' '.join([to_indexable(parsed_addr) for parsed_addr in msg.cc_addr])
                indexer.index_text(cc, 3)
                indexer.index_text(cc, 3, 'XCC')
            if msg.bcc_addr is not None:
                bcc = ' '.join([to_indexable(parsed_addr) for parsed_addr in msg.bcc_addr])
                indexer.index_text(bcc, 3)
                indexer.index_text(bcc, 3, 'XBCC')
            # "Values" are other data that you can use for e.g. sorting by
            # date
            doc.add_value(0, x_.sortable_serialise(
                timegm(msg.internaldate.utctimetuple())))
            database.replace_document(msg.id, doc)

        done += 1
        log.info("Indexed %i of %i (%.2f%%)" % (done, total, done/total*100))

    indexed_msgs = {k for k in database.metadata_keys()}
    msgs = [id for id, in db_session.query(distinct(Message.id)).filter_by(
            id=namespace.id)]
    to_delete = indexed_msgs - msgs
    log.info("{0} documents to remove...".format(len(to_delete)))

    for msg_id in to_delete:
        database.delete_document(msg_id)

    database.close()
    log.info("done.")

class SearchService(object):
    """ ZeroRPC interface to searching. """
    def index(self, namespace_id):
        """ Trigger index update for this namespace. """
        with session_scope() as db_session:
            namespace = db_session.query(Namespace).get(namespace_id)
            assert namespace is not None
            gen_search_index(db_session, namespace)
        return "OK"

    def search(self, namespace_id, query_string, limit=10):
        """ returns [(message.id, relevancerank), ...]

            fulltext is fulltext of the matching *part*, not the entire
            message.
        """
        log.info("query '{0}' for namespace '{1}'".format(query_string, namespace_id))
        # Open the database for searching.
        database = x_.Database(db_path_for(namespace_id))

        # Start an enquire session.
        enquire = x_.Enquire(database)

        # Parse the query string to produce a Xapian::Query object.
        qp = x_.QueryParser()
        stemmer = x_.Stem("english")
        qp.set_stemmer(stemmer)
        qp.set_database(database)
        qp.set_stemming_strategy(x_.QueryParser.STEM_SOME)

        # Set up custom prefixes.
        qp.add_prefix("subject", "XSUBJECT")
        qp.add_prefix("from", "XFROM")
        qp.add_prefix("to", "XTO")
        qp.add_prefix("cc", "XCC")
        qp.add_prefix("bcc", "XBCC")

        results = get_results(qp, enquire, query_string, limit)

        if not results:
            log.info("No results found; trying spelling correction.")
            # XXX somehow signify to the user that their query was corrected?
            # unless, of course, we also get nothing back with the corrected
            # query
            log.info("Corrected query string: {0}".format(
                    qp.get_corrected_query_string()))
            results = get_results(qp, enquire,
                    qp.get_corrected_query_string(), limit)

        # Clean up.
        database.close()

        return results

def get_results(qp, enquire, query_string, limit):
    query = qp.parse_query(query_string, QUERY_FLAGS)
    log.info("Parsed query is: %s" % str(query))

    # Find the top N results for the query.
    enquire.set_query(query)
    matches = enquire.get_mset(0, limit)

    # Display the results.
    log.info("%i results found." % matches.get_matches_estimated())
    log.info("Results 1-%i:" % matches.size())

    return [(m.docid, m.rank) for m in matches]
