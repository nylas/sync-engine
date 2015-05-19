"""make address fields non-null.

Revision ID: 2d05e116bdb7
Revises: 5143154fb1a2
Create Date: 2014-07-17 22:13:41.792085

"""

# revision identifiers, used by Alembic.
revision = '2d05e116bdb7'
down_revision = '4fd3fcd46a3b'

from alembic import op
from sqlalchemy import func, or_
from sqlalchemy.dialects import mysql


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    from inbox.models.session import session_scope
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Message(Base):
        __table__ = Base.metadata.tables['message']

    with session_scope(versioned=False) \
            as db_session:
        null_field_count = db_session.query(func.count(Message.id)). \
            filter(or_(Message.from_addr.is_(None),
                       Message.to_addr.is_(None),
                       Message.cc_addr.is_(None),
                       Message.bcc_addr.is_(None))).scalar()
        print 'messages to migrate:', null_field_count
        if int(null_field_count):
            for message in db_session.query(Message):
                for attr in ('to_addr', 'from_addr', 'cc_addr', 'bcc_addr'):
                    if getattr(message, attr) is None:
                        setattr(message, attr, [])
                print '.',
        db_session.commit()

    print 'making addrs non-nullable'

    op.alter_column('message', 'bcc_addr', existing_type=mysql.TEXT(),
                    nullable=False)
    op.alter_column('message', 'cc_addr', existing_type=mysql.TEXT(),
                    nullable=False)
    op.alter_column('message', 'from_addr', existing_type=mysql.TEXT(),
                    nullable=False)
    op.alter_column('message', 'to_addr', existing_type=mysql.TEXT(),
                    nullable=False)


def downgrade():
    op.alter_column('message', 'to_addr', existing_type=mysql.TEXT(),
                    nullable=True)
    op.alter_column('message', 'from_addr', existing_type=mysql.TEXT(),
                    nullable=True)
    op.alter_column('message', 'cc_addr', existing_type=mysql.TEXT(),
                    nullable=True)
    op.alter_column('message', 'bcc_addr', existing_type=mysql.TEXT(),
                    nullable=True)
