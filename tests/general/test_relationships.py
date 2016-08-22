import json

from inbox.models import Category, Message, MessageCategory, Thread

from tests.util.base import add_fake_message, add_fake_thread
from tests.api.base import new_api_client


def test_category_delete(db, gmail_account):
    """ Ensure that all associated MessageCategories are deleted
        when a Category is deleted """

    api_client = new_api_client(db, gmail_account.namespace)
    po_data = api_client.post_data('/labels/',
                                   {"display_name": "Test_Label"})
    assert po_data.status_code == 200

    category_public_id = json.loads(po_data.data)['id']
    category = db.session.query(Category).filter(
        Category.public_id == category_public_id).one()
    category_id = category.id

    for i in xrange(10):
        generic_thread = add_fake_thread(db.session,
                                         gmail_account.namespace.id)
        gen_message = add_fake_message(db.session,
                                       gmail_account.namespace.id,
                                       generic_thread)
        data = {"label_ids": [category_public_id]}
        resp = api_client.put_data('/messages/{}'.
                                   format(gen_message.public_id), data)
        assert resp.status_code == 200

    associated_mcs = db.session.query(MessageCategory). \
        filter(MessageCategory.category_id == category_id).all()
    assert len(associated_mcs) == 10

    db.session.delete(category)
    db.session.commit()

    assert db.session.query(MessageCategory). \
        filter(MessageCategory.category_id == category_id).all() == []


def test_message_delete(db, gmail_account):
    """ Ensure that all associated MessageCategories are deleted
        when a Message is deleted """

    api_client = new_api_client(db, gmail_account.namespace)

    generic_thread = add_fake_thread(db.session, gmail_account.namespace.id)
    gen_message = add_fake_message(db.session,
                                   gmail_account.namespace.id,
                                   generic_thread)

    category_ids = []
    for i in xrange(10):
        po_data = api_client.post_data('/labels/',
                                       {"display_name": str(i)})
        assert po_data.status_code == 200

        category_ids.append(json.loads(po_data.data)['id'])

    data = {"label_ids": category_ids}
    resp = api_client.put_data('/messages/{}'.
                               format(gen_message.public_id), data)
    assert resp.status_code == 200

    associated_mcs = db.session.query(MessageCategory). \
        filter(MessageCategory.message_id == gen_message.id).all()
    assert len(associated_mcs) == 10

    db.session.delete(gen_message)
    db.session.commit()

    assert db.session.query(MessageCategory). \
        filter(MessageCategory.message_id == gen_message.id).all() == []


def test_thread_delete(db, gmail_account):
    """ Ensure that all associated Messages are deleted
        when a Thread is deleted."""

    generic_thread = add_fake_thread(db.session, gmail_account.namespace.id)
    generic_message = add_fake_message(db.session,
                                       gmail_account.namespace.id,
                                       generic_thread)
    assert db.session.query(Thread). \
        filter(Thread.id == generic_thread.id).all() == [generic_thread]
    assert db.session.query(Message). \
        filter(Message.id == generic_message.id).all() == [generic_message]

    db.session.delete(generic_thread)
    db.session.commit()

    assert db.session.query(Thread). \
        filter(Thread.id == generic_thread.id).all() == []
    assert db.session.query(Message). \
        filter(Message.id == generic_message.id).all() == []
