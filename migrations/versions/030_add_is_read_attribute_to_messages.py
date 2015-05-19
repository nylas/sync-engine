"""add is_read attribute to messages

Revision ID: 1b6ceae51b43
Revises: 52a9a976a2e0
Create Date: 2014-05-15 23:57:34.159260

"""

# revision identifiers, used by Alembic.
revision = '1b6ceae51b43'
down_revision = '52a9a976a2e0'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref


def upgrade():
    op.add_column('message',
                  sa.Column('is_read', sa.Boolean(),
                            server_default=sa.sql.expression.false(),
                            nullable=False))

    op.alter_column('usertagitem', 'created_at',
                    existing_type=mysql.DATETIME(), nullable=False)
    op.alter_column('usertagitem', 'updated_at',
                    existing_type=mysql.DATETIME(), nullable=False)

    from inbox.models.session import session_scope
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Message(Base):
        __table__ = Base.metadata.tables['message']

    class ImapUid(Base):
        __table__ = Base.metadata.tables['imapuid']
        message = relationship('Message',
                               backref=backref('imapuids',
                                               primaryjoin='and_('
                                               'Message.id == ImapUid.message_id, '
                                               'ImapUid.deleted_at == None)'),
                               primaryjoin='and_('
                               'ImapUid.message_id == Message.id,'
                               'Message.deleted_at == None)')

    with session_scope(versioned=False) as db_session:
        for uid in db_session.query(ImapUid).yield_per(500):
            if uid.is_seen:
                uid.message.is_read = True

        db_session.commit()


def downgrade():
    op.alter_column('usertagitem', 'updated_at',
                    existing_type=mysql.DATETIME(), nullable=True)
    op.alter_column('usertagitem', 'created_at',
                    existing_type=mysql.DATETIME(), nullable=True)
    op.drop_column('message', 'is_read')
