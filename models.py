import os
import sys

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text
from sqlalchemy import ForeignKey, Table, Index, func

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

import logging as log

# g contacts imports
import getopt
import getpass
import atom
import gdata.contacts.data
import gdata.contacts.client


class Contact(Base):
  """ Inbox-specific sessions. """
  __tablename__ = 'contact'

  id = Column(Integer, primary_key=True, autoincrement=True)
  email = Column(String(64))
  name = Column(String(64))

  google_id = Column(String(64), unique=True, index=True)


  updated_at = Column(DateTime, server_default=func.now(), onupdate=func.current_timestamp())
  created_at = Column(DateTime, server_default=func.now())

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
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

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

  return gd_client

def sync_contacts():
  db_session.add_all(contacts_to_commit)
  db_session.commit()

def main():
  gd_client = get_gd_client()
  db_session = connect_to_db()
  contacts = []
  for contact in gd_client.GetContacts().entry:
    print contact
    c = Contact()
    emails = filter(lambda email: email.primary, contact.email)
    
    c.name = contact.name.full_name.text
    c.google_id = contact.id.text
    if emails:
      c.email = emails[0].address

    contacts.append(c)
  db_session.add_all(contacts)
  db_session.commit()
   
  print db_session.query(Contact).all()

if __name__ == "__main__":
  main()
