""" Tests for delta logging. """

from pytest import fixture

from sqlalchemy import create_engine, Column, Enum, String, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import as_declarative, declared_attr

from inbox.sqlalchemy_ext.revision import versioned_session, Revision, gen_rev_role


@as_declarative()
class Base(object):
    id = Column(Integer, primary_key=True, autoincrement=True)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


class MonkeyRevision(Base, Revision):
    pass

HasRevisions = gen_rev_role(MonkeyRevision)


class Monkey(Base, HasRevisions):
    type = Column(Enum('chimpanzee', 'gorilla', 'rhesus'), nullable=False)
    name = Column(String(40), nullable=True)
    age = Column(Integer, nullable=False)

    @property
    def favorite_food(self):
        return 'banana'

    def get_versioned_properties(self):
        return {'favorite_food': self.favorite_food}


class Tree(Base):
    type = Column(Enum('maple', 'palm', 'fir'), nullable=False)
    location = Column(String(40), nullable=False)


@fixture(scope='function')
def db_session(request):
    # engine = create_engine('sqlite:///test.db')
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    session = versioned_session(sessionmaker()(bind=engine), MonkeyRevision,
                                HasRevisions)
    return session


def test_basics(db_session):
    """ Tests insert, update, delete. """
    randy = Monkey(type='chimpanzee', name='Randy', age=3)
    bob = Monkey(type='rhesus', name='Bob', age=5)

    db_session.add_all([randy, bob])
    db_session.commit()

    # verify that rev 1 and rev 2 were committed
    txns = db_session.query(MonkeyRevision).all()
    assert len(txns) == 2, "two transactions created"
    randy_insert_txn, bob_insert_txn = txns
    assert randy_insert_txn.command == 'insert'
    assert randy_insert_txn.table_name == 'monkey'
    assert randy.revisions[0].record_id == randy_insert_txn.id
    assert isinstance(randy.revisions[0], MonkeyRevision)
    assert bob_insert_txn.command == 'insert'
    assert bob_insert_txn.table_name == 'monkey'
    assert bob.revisions[0].record_id == bob_insert_txn.id
    assert isinstance(bob.revisions[0], MonkeyRevision)

    # triggering dirty obj in session shouldn't create a rev w/no delta
    bob.age = 5
    db_session.commit()
    assert bob.revisions[-1].command == 'insert'

    bob.age += 1
    db_session.commit()
    assert bob.revisions[-1].command == 'update'
    assert bob.revisions[-1].delta == dict(age=6)

    db_session.delete(randy)
    db_session.commit()
    delete_txn = db_session.query(MonkeyRevision)\
        .filter_by(command='delete').first()
    assert delete_txn.command == 'delete'


def test_skip_rev_create(db_session):
    """ ORM Classes without HasRevisions shouldn't generate revisions. """
    tree = Tree(type='palm', location='Dolores Park')
    db_session.add(tree)
    db_session.commit()
    assert not hasattr(tree, 'revisions')
    tree_txns = db_session.query(MonkeyRevision).filter_by(
        table_name='tree', record_id=tree.id).all()
    assert not tree_txns


def test_save_additional_data(db_session):
    db_session.add(Monkey(type='chimpanzee', name='Alice', age=22))
    db_session.commit()

    txn = db_session.query(MonkeyRevision).one()
    assert txn.additional_data == {'favorite_food': 'banana'}


# TODO: Test updates on objects with relationships.
