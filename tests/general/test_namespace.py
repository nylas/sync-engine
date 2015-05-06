from pytest import yield_fixture

from inbox.models import *

from tests.util.base import TestDB, absolute_path


# TODO[k]: FIX standard test dump to have right schema instead.
@yield_fixture(scope='function')
def latest_db(config):
    dumpfile = absolute_path('data/latest_dump.sql')
    testdb = TestDB(config, dumpfile)
    yield testdb
    testdb.teardown()


def test_namespace_deletion(latest_db):
    namespace = latest_db.session.query(Namespace).first()
    namespace_id = namespace.id

    account_id = namespace.account.id
    models = [Thread, Message, Block, Contact, Event, Transaction]

    account = latest_db.session.query(Account).get(account_id)
    assert account

    for m in models:
        assert latest_db.session.query(m).filter(
            m.namespace_id == namespace_id).count() != 0

    # Delete
    latest_db.session.execute(
        '''DELETE FROM message WHERE namespace_id = :namespace_id;''',
        {'namespace_id': namespace_id})
    latest_db.session.delete(account)
    latest_db.session.commit()

    account = latest_db.session.query(Account).get(account_id)
    assert not account

    for m in models:
        assert latest_db.session.query(m).filter(
            m.namespace_id == namespace_id).count() == 0
