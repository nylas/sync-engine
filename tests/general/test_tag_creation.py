from inbox.models import Namespace, Tag

CANONICAL_TAG_NAMES = {'inbox', 'archive', 'drafts', 'sending', 'sent', 'spam',
                       'starred', 'trash', 'unread', 'unseen', 'attachment'}


def test_canonical_tags_created_for_namespace(db):
    new_namespace = Namespace()
    db.session.add(new_namespace)
    db.session.commit()
    tags = db.session.query(Tag).filter(Tag.namespace_id ==
                                        new_namespace.id).all()
    assert {tag.name for tag in tags} == CANONICAL_TAG_NAMES
