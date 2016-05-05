from sqlalchemy import (Column, BigInteger, Integer, Text, ForeignKey, Enum,
                        Index, String)
from sqlalchemy.orm import relationship

from inbox.sqlalchemy_ext.util import JSON
from inbox.models.base import MailSyncBase
from inbox.models.mixins import UpdatedAtMixin, DeletedAtMixin
from inbox.models.namespace import Namespace


def schedule_action(func_name, record, namespace_id, db_session, **kwargs):
    # Ensure that the record's id is non-null
    db_session.flush()

    account = db_session.query(Namespace).get(namespace_id).account
    log_entry = account.actionlog_cls.create(
        action=func_name,
        table_name=record.__tablename__,
        record_id=record.id,
        namespace_id=namespace_id,
        extra_args=kwargs)
    db_session.add(log_entry)


class ActionLog(MailSyncBase, UpdatedAtMixin, DeletedAtMixin):
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False,
                          index=True)
    namespace = relationship('Namespace')

    action = Column(Text(40), nullable=False)
    record_id = Column(BigInteger, nullable=False)
    table_name = Column(Text(40), nullable=False)
    status = Column(Enum('pending', 'successful', 'failed'),
                    server_default='pending')
    retries = Column(Integer, server_default='0', nullable=False)

    extra_args = Column(JSON, nullable=True)

    @classmethod
    def create(cls, action, table_name, record_id, namespace_id, extra_args):
        return cls(action=action, table_name=table_name, record_id=record_id,
                   namespace_id=namespace_id, extra_args=extra_args)

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_identity': 'actionlog',
                       'polymorphic_on': discriminator}

Index('ix_actionlog_status_retries', ActionLog.status, ActionLog.retries)
Index('idx_actionlog_status_type', ActionLog.status, ActionLog.discriminator)
