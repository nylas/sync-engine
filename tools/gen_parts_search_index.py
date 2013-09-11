#!/usr/bin/env python
# use this to generate a xapian index of message parts
import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..')))

import sys
import xappy
from config import setup_env
setup_env()

from server.models import db_session, MessageMeta

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

def main():
    # set up the database
    conn = xappy.IndexerConnection('parts.db')

    # start simple: just id, date, subject, and plain text
    conn.add_field_action('id', xappy.FieldActions.SORTABLE, type="float")
    conn.add_field_action('date', xappy.FieldActions.SORTABLE, type="date")
    conn.add_field_action('date', xappy.FieldActions.STORE_CONTENT)
    conn.add_field_action('subject', xappy.FieldActions.INDEX_FREETEXT, language='en')
    conn.add_field_action('subject', xappy.FieldActions.STORE_CONTENT)
    conn.add_field_action('text', xappy.FieldActions.INDEX_FREETEXT, language='en')
    conn.add_field_action('text', xappy.FieldActions.STORE_CONTENT)

    # load all messages that we want to process from the database
    email_address = 'spang@inboxapp.com'
    msg_query = db_session.query(MessageMeta).filter_by(g_email=email_address).options(joinedload('parts'))
    print "Have {0} messages to process".format(msg_query.count())
    print

    # for each message part, create unprocessed documents with date/subject/to/from
    # metadata and the plaintext part, and then process them!
    for msg in msg_query:
        plain_parts = [part for part in msg.parts \
                if part._content_type_common == 'text/plain']
        html_parts = [part for part in msg.parts \
                if part._content_type_common == 'text/html']
        print ".",
        print "{0}: {1} text/plain, {2} text/html".format(
                msg.g_msgid, len(plain_parts), len(html_parts))
        # XXX do we really always want the first part?
        text = None
        if plain_parts:
            text = plain_parts[0].get_data()
        elif html_parts:
            text = strip_tags(html_parts[0].get_data())

        if text is not None:
            doc = xappy.UnprocessedDocument()
            doc.fields.append(xappy.Field("subject", msg.subject))
            doc.fields.append(xappy.Field("date", msg.internaldate))
            doc.fields.append(xappy.Field("text", text))
            conn.add(doc)

    print
    print "done."

    # clean up
    conn.flush()
    conn.close()

if __name__ == '__main__':
    sys.exit(main())
