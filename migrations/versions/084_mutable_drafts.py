"""Mutable drafts

Revision ID: 10db12da2005
Revises: 43e5867a6ef1
Create Date: 2014-08-22 22:04:10.763048

"""

# revision identifiers, used by Alembic.
revision = '10db12da2005'
down_revision = '10a1129fe685'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def page_query(q):
    CHUNK_SIZE = 1000
    offset = 0
    while True:
        r = False
        for elem in q.limit(CHUNK_SIZE).offset(offset):
            r = True
            yield elem
        offset += CHUNK_SIZE
        if not r:
            break


def upgrade():
    from inbox.sqlalchemy_ext.util import JSON

    op.add_column('actionlog',
                  sa.Column('extra_args', JSON(), nullable=True))

    op.add_column('message',
                  sa.Column('version', mysql.BINARY(16), nullable=True))

    op.drop_constraint('message_ibfk_3', 'message', type_='foreignkey')

    from inbox.ignition import main_engine
    from inbox.models.session import session_scope

    engine = main_engine(pool_size=1, max_overflow=0)
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)

    class Message(Base):
        __table__ = Base.metadata.tables['message']

    # Delete old draft versions, set message.version=public_id on the latest
    # one.
    with session_scope(ignore_soft_deletes=False, versioned=False) as \
            db_session:

        parent_draft_ids = [d for d, in db_session.query(
            Message.parent_draft_id).filter(
            Message.is_created == True,
            Message.is_draft == True,
            Message.parent_draft_id.isnot(None)).all()]

        q = db_session.query(Message).filter(
            Message.is_created == True,
            Message.is_draft == True)

        for d in page_query(q):
            if d.id in parent_draft_ids:
                db_session.delete(d)
            else:
                d.version = d.public_id
                db_session.add(d)

        db_session.commit()

    op.drop_column('message', 'parent_draft_id')


def downgrade():
    raise Exception('No.')
