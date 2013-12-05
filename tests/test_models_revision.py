""" Tests for delta logging """

import pytest

from sqlalchemy import create_engine, Column, Enum, String, Integer
from sqlalchemy.orm import sessionmaker

from inbox.sqlalchemy.revision import versioned_session, Revision, HasRevisions
from inbox.sqlalchemy.util import Base

class Monkey(Base, HasRevisions):
    type = Column(Enum('chimpanzee', 'gorilla', 'rhesus'), nullable=False)
    name = Column(String(40), nullable=True)
    age = Column(Integer, nullable=False)

@pytest.fixture(scope='session')
def db_session(request):
    # engine = create_engine('sqlite:///test.db')
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    session = sessionmaker()(bind=engine)
    versioned_session(session, rev_cls=Revision)
    return session

def test_versioning(db_session, config):
    """ Tests insert, update, deletea. """
    randy = Monkey(type='chimpanzee', name='Randy', age=3)
    bob = Monkey(type='rhesus', name='Bob', age=5)

    db_session.add_all([randy, bob])
    db_session.commit()

    # verify that rev 1 and rev 2 were committed
    txns = db_session.query(Revision).all()
    assert len(txns) == 2, "two transactions created"
    randy_insert_txn, bob_insert_txn = txns
    assert randy_insert_txn.command == 'insert'
    assert randy_insert_txn.table_name == 'monkey'
    assert randy.revisions[0].record_id == randy_insert_txn.id
    assert isinstance(randy.revisions[0], Revision)
    assert bob_insert_txn.command == 'insert'
    assert bob_insert_txn.table_name == 'monkey'
    assert bob.revisions[0].record_id == bob_insert_txn.id
    assert isinstance(bob.revisions[0], Revision)

    bob.age += 1
    db_session.commit()
    assert bob.revisions[-1].command == 'update'
    assert bob.revisions[-1].delta == dict(age=6)

    db_session.delete(randy)
    db_session.commit()
    delete_txn = db_session.query(Revision).filter_by(command='delete').first()
    assert delete_txn.command == 'delete'

# TODO: Test updates on objects with relationships.
