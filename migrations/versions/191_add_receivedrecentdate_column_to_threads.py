"""add receivedrecentdate column to threads

Revision ID: 2758cefad87d
Revises: 246a6bf050bc
Create Date: 2015-07-17 20:40:31.951910

"""

# revision identifiers, used by Alembic.
revision = '2758cefad87d'
down_revision = '246a6bf050bc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('thread'):
        return
    op.add_column('thread',
                  sa.Column('receivedrecentdate', sa.DATETIME(),
                            server_default=sa.sql.null(),
                            nullable=True))
    op.create_index('ix_thread_namespace_id_receivedrecentdate', 'thread',
                    ['namespace_id', 'receivedrecentdate'], unique=False)


def downgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('thread'):
        return
    op.drop_column('thread', 'receivedrecentdate')
    op.drop_index('ix_thread_namespace_id_receivedrecentdate',
                  table_name='thread')
