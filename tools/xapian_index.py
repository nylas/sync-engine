#!/usr/bin/env python
#
# Index each paragraph of a text file as a Xapian document.
#
# Copyright (C) 2003 James Aylett
# Copyright (C) 2004,2007 Olly Betts
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301
# USA

import xapian

import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..')))
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


if len(sys.argv) != 2:
    print >> sys.stderr, "Usage: %s PATH_TO_DATABASE" % sys.argv[0]
    sys.exit(1)

try:
    # Open the database for update, creating a new database if necessary.
    database = xapian.WritableDatabase(sys.argv[1], xapian.DB_CREATE_OR_OPEN)

    indexer = xapian.TermGenerator()
    stemmer = xapian.Stem("english")
    indexer.set_stemmer(stemmer)

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

        # XXX also index attachments (add a 'type' field or something to
        # differentiate)

        if text is not None:
            doc = xapian.Document()
            doc.set_data(text)

            indexer.set_document(doc)
            indexer.index_text(text)
            database.replace_document(msg.id, doc)

    print
    print "done."

except Exception, e:
    print >> sys.stderr, "Exception: %s" % str(e)
    sys.exit(1)
