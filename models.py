# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
import os
import sys
import datetime
import dateutil.parser
import json

from sqlalchemy import *
import sqlalchemy.orm

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

import logging as log

# g contacts imports
import getopt
import getpass
import atom
import gdata.contacts.data
import gdata.contacts.client


class User(Base):
    __tablename__ = "user"
    email = Column(String(64), primary_key=True)

    last_synced = Column(DateTime)

class Contact(Base):
    """ Inbox-specific sessions. """
    __tablename__ = 'contact'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(64))
    name = Column(String(64))

    google_id = Column("google_id", String(64))

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.current_timestamp())
    created_at = Column(DateTime, server_default=func.now())

    source = Column("source", Enum("local", "remote")) 

    UniqueConstraint("google_id", "source")
    def cereal(self):
        return dict(email=self.email,
                    name=self.name,
                    google_id=self.google_id)

    def __repr__(self):
        return str(self.name) + ", " + str(self.email) + ", " + str(self.source)

def connect_to_db():
## Make the tables
    from sqlalchemy import create_engine
    DB_URI = "sqlite:///contacts.db"

    engine = create_engine(DB_URI)

    def init_db():
            Base.metadata.create_all(engine)

    init_db()

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker()
    Session.configure(bind=engine)

# A single global database session per Inbox instance is good enough for now.
    db_session = Session()
    return db_session

def get_gd_client():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['user=', 'pw='])
    except getopt.error, msg:
        print 'python contacts_example.py --user [username] --pw [password]'
        sys.exit(2)

    user = ''
    pw = ''
# Process options
    for option, arg in opts:
        if option == '--user':
            user = arg
        elif option == '--pw':
            pw = arg

    while not user:
        print 'NOTE: Please run these tests only with a test account.'
        user = raw_input('Please enter your username: ')
    while not pw:
        pw = getpass.getpass()
        if not pw:
            print 'Password cannot be blank.'

    try:
        gd_client = gdata.contacts.client.ContactsClient(source='GoogleInc-ContactsPythonSample-1')
        gd_client.ClientLogin(user, pw, gd_client.source)
    except gdata.client.BadAuthentication:
        print 'Invalid user credentials given.'
        return

    return user, gd_client

def sync_contacts():
    db_session.add_all(contacts_to_commit)
    db_session.commit()

def main():
    user_email, gd_client = get_gd_client()
    db_session = connect_to_db()
    contacts = []
    try:
        user = db_session.query(User).filter_by(email = user_email).one()
    except sqlalchemy.orm.exc.NoResultFound:
        user = User()
        user.email = user_email
        user.last_synced = datetime.datetime.fromtimestamp(0)

    updated_min = user.last_synced.isoformat()
    query = gdata.contacts.client.ContactsQuery()
    query.updated_min = updated_min
    feed = gd_client.GetContacts(q = query) 

    existing_contacts = db_session.query(Contact).filter_by(source = "local").all()
    cached_contacts = db_session.query(Contact).filter_by(source = "remote").all()

    contact_dict = {}
    for contact in existing_contacts:
        contact_dict[contact.google_id] = contact
    
    cached_dict = {}
    for contact in cached_contacts:
        cached_dict[contact.google_id] = contact

    for contact in gd_client.GetContacts(q = query).entry:
        emails = filter(lambda email: email.primary, contact.email)
        
        google_result = {
            "name": contact.name.full_name.text,
            "google_id": contact.id.text,
            "updated_at": dateutil.parser.parse(contact.updated.text)
        }

        if emails:
            google_result["email"] = emails[0].address
        
        # make an object out of the google result
        c = Contact(source='local', **google_result)

        if c.google_id in contact_dict:
            existing = contact_dict[c.google_id]
            if c.google_id in cached_dict:
                # now we can get a diff and merge
                cached = cached_dict[c.google_id]

                if cached.name != c.name:
                    existing.name = c.name
                if cached.email != c.email:
                    existing.email = c.email
            
            else:
                # no diff, just overwrite it
                existing = contact_dict[c.google_id]
                existing.name = c.name
                existing.email = c.email
            
        else:
            # doesn't exist yet, add both remote and local
            db_session.add(c)
            cached = Contact(**google_result)
            cached.source = "remote"
            db_session.add(cached)

    user.last_synced = datetime.datetime.now()
    db_session.add(user)
    db_session.commit()

if __name__ == "__main__":
    main()
