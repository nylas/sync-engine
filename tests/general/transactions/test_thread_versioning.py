from inbox.models import Tag
from tests.util.base import thread, default_namespace, add_fake_message


def test_thread_tag_updates_increment_version(db, thread, default_namespace):
    assert thread.version == 0
    new_tag = Tag(name='foo', namespace=default_namespace)
    thread.apply_tag(new_tag)
    db.session.commit()
    assert thread.version == 1
    thread.remove_tag(new_tag)
    db.session.commit()
    assert thread.version == 2


def test_adding_and_removing_message_on_thread_increments_version(
        db, thread, default_namespace):
    assert thread.version == 0
    message = add_fake_message(db.session, default_namespace.id, thread)
    thread.messages.remove(message)
    db.session.commit()
    assert thread.version == 2
