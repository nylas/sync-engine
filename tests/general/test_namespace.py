from tests.util.base import add_fake_account, add_fake_thread, add_fake_message


def test_namespace_deletion(db):
    from inbox.models import (Namespace, Account, Thread, Message, Block,
                              Contact, Event, Transaction)
    from inbox.models.util import delete_namespace

    models = [Thread, Message, Block, Contact, Event, Transaction]

    namespace = db.session.query(Namespace).first()
    namespace_id = namespace.id
    account_id = namespace.account.id

    account = db.session.query(Account).get(account_id)
    assert account

    for m in models:
        assert db.session.query(m).filter(
            m.namespace_id == namespace_id).count() != 0

    fake_account = add_fake_account(db.session)
    fake_account_id = fake_account.id

    assert fake_account_id != account.id and \
        fake_account.namespace.id != namespace_id

    thread = add_fake_thread(db.session, fake_account.namespace.id)
    thread_id = thread.id

    message = add_fake_message(db.session, fake_account.namespace.id, thread)
    message_id = message.id

    # Delete namespace, verify data corresponding to this namespace /only/
    # is deleted
    delete_namespace(account_id, namespace_id)
    db.session.commit()

    account = db.session.query(Account).get(account_id)
    assert not account

    for m in models:
        assert db.session.query(m).filter(
            m.namespace_id == namespace_id).count() == 0

    fake_account = db.session.query(Account).get(fake_account_id)
    assert fake_account

    thread = db.session.query(Thread).get(thread_id)
    message = db.session.query(Message).get(message_id)
    assert thread and message
