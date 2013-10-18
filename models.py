from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text
from sqlalchemy import ForeignKey, Table, Index, func

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

import logging as log


class Contact(Base):
    """ Inbox-specific sessions. """
    __tablename__ = 'contact'

    id = Column(Integer, primary_key=True, autoincrement=True)

    token = Column(String(40))
    # sessions have a many-to-one relationship with users
    user_id = Column(Integer, nullable=False)


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
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4


c = Contact()
c.token = "hi world"
c.user_id = 2541

contacts_to_commit = [c]

db_session.add_all(contacts_to_commit)
db_session.commit()

