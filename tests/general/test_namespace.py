from pytest import yield_fixture

from tests.util.base import TestDB, absolute_path


# TODO[k]: FIX standard test dump to have right schema instead.
@yield_fixture(scope='function')
def latest_db(config):
    dumpfile = absolute_path('data/base_dump.sql')
    testdb = TestDB(config, dumpfile)
    yield testdb
    testdb.teardown()


def test_namespace_deletion(latest_db):
    from inbox.models import *
    from inbox.models.util import delete_namespace

    namespace = latest_db.session.query(Namespace).first()
    namespace_id = namespace.id

    account_id = namespace.account.id
    models = [Thread, Message, Block, Contact, Event, Transaction]

    account = latest_db.session.query(Account).get(account_id)
    assert account

    for m in models:
        assert latest_db.session.query(m).filter(
            m.namespace_id == namespace_id).count() != 0

    # Delete namespace
    delete_namespace(account_id, namespace_id)
    latest_db.session.commit()

    account = latest_db.session.query(Account).get(account_id)
    assert not account

    for m in models:
        assert latest_db.session.query(m).filter(
            m.namespace_id == namespace_id).count() == 0
