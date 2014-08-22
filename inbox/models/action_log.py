from sqlalchemy import Column, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false

from inbox.sqlalchemy_ext.util import JSON
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace

ADD_TAG_ACTIONS = {
    'inbox': 'unarchive',
    'archive': 'archive',
    'starred': 'star',
    'unread': 'mark_unread',
    'spam': 'mark_spam',
    'trash': 'mark_trash'
}

REMOVE_TAG_ACTIONS = {
    'inbox': 'archive',
    'archive': 'unarchive',
    'starred': 'unstar',
    'unread': 'mark_read',
    'spam': 'unmark_spam',
    'trash': 'unmark_trash'
}


def schedule_action_for_tag(tag_public_id, thread, db_session, tag_added):
    if tag_added:
        action = ADD_TAG_ACTIONS.get(tag_public_id)
    else:
        action = REMOVE_TAG_ACTIONS.get(tag_public_id)
    if action is not None:
        schedule_action(action, thread, thread.namespace_id, db_session)


def schedule_action(func_name, record, namespace_id, db_session, **kwargs):
    db_session.flush()  # Ensure that the record's id is non-null
    log_entry = ActionLog(
        action=func_name,
        table_name=record.__tablename__,
        record_id=record.id,
        namespace_id=namespace_id,
        extra_args=kwargs)
    db_session.add(log_entry)


class ActionLog(MailSyncBase):
    # STOPSHIP(emfree) should we set ondelete='CASCADE' here?
    namespace_id = Column(ForeignKey(Namespace.id), nullable=False, index=True)
    namespace = relationship(
        'Namespace',
        primaryjoin='and_(ActionLog.namespace_id==Namespace.id, '
                    'Namespace.deleted_at.is_(None))')

    action = Column(Text(40), nullable=False)
    record_id = Column(Integer, nullable=False)
    table_name = Column(Text(40), nullable=False)
    executed = Column(Boolean, server_default=false(), nullable=False)

    extra_args = Column(JSON, nullable=True)
