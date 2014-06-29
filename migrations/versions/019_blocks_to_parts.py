"""Save "Blocks" (attachments) as "Parts" since now
  "Blocks" are general uploaded files

Revision ID: 5a787816e2bc
Revises: 223041bb858b
Create Date: 2014-04-28 22:09:00.652851

"""

# revision identifiers, used by Alembic.
revision = '5a787816e2bc'
down_revision = '223041bb858b'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base


chunk_size = 250


def upgrade():
    from inbox.models.session import session_scope, Session
    from inbox.ignition import engine

    from inbox.models import (Part, Namespace,
                                                 Message, Thread)
    from inbox.sqlalchemy_ext.util import JSON

    print 'Creating table for parts...'
    op.create_table('part',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('message_id', sa.Integer(), nullable=True),
                    sa.Column('walk_index', sa.Integer(), nullable=True),
                    sa.Column('content_disposition', sa.Enum(
                        'inline', 'attachment'), nullable=True),
                    sa.Column(
                        'content_id', sa.String(length=255), nullable=True),
                    sa.Column('misc_keyval', JSON(), nullable=True),
                    sa.Column('is_inboxapp_attachment', sa.Boolean(),
                              server_default=sa.sql.expression.false(),
                              nullable=True),
                    sa.ForeignKeyConstraint(
                        ['id'], ['block.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(
                        ['message_id'], ['message.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('message_id', 'walk_index')
                    )

    print 'Reflecting old block table schema'
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Block_(Base):  # old schema, reflected from database table
        __table__ = Base.metadata.tables['block']

    print 'Adding namespace_id column to blocks ',
    op.add_column(
        u'block', sa.Column('namespace_id', sa.Integer(), nullable=False))

    print 'Migrating from blocks to parts'
    new_parts = []
    with session_scope() as db_session:
        for block in db_session.query(Block_).yield_per(chunk_size):

            # Move relevant fields
            p = Part()
            p.size = block.size
            p.data_sha256 = block.data_sha256
            p.message_id = block.message_id
            p.walk_index = block.walk_index
            p.content_disposition = block.content_disposition
            p.content_id = block.content_id
            p.misc_keyval = block.misc_keyval
            p.is_inboxapp_attachment

            old_namespace = db_session.query(Namespace) \
                .join(Message.thread, Thread.namespace) \
                .filter(Message.id == block.message_id).one()
            p.namespace_id = old_namespace.id

            # Commit after column modifications
            new_parts.append(p)

        print 'Deleting old blocks (now parts)... ',
        db_session.query(Block_).delete()
        db_session.commit()
        print 'Done!'

    print 'Removing `message_id` constraint from block'
    op.drop_constraint('block_ibfk_1', 'block', type_='foreignkey')

    print 'Creating foreign key for block -> namespace on block'
    op.create_foreign_key('block_ibfk_1', 'block', 'namespace',
                          ['namespace_id'], ['id'], ondelete='CASCADE')

    print 'Dropping old block columns which are now in part'
    op.drop_column(u'block', u'walk_index')
    op.drop_column(u'block', u'content_disposition')
    op.drop_column(u'block', u'misc_keyval')
    op.drop_column(u'block', u'content_id')
    op.drop_column(u'block', u'is_inboxapp_attachment')
    op.drop_constraint(u'message_id', 'block', type_='unique')
    op.drop_column(u'block', u'message_id')

    # Note: here we use the regular database session, since the transaction
    # log requires the `namespace` property on objects. We've set the
    # `namespace_id` foreign key, but need to commit the object before the
    # SQLalchemy reference is valid
    no_tx_session = Session(autoflush=True, autocommit=False)
    no_tx_session.add_all(new_parts)
    no_tx_session.commit()

    print 'Done migration blocks to parts!'


def downgrade():
    raise Exception("This will lose data!")
