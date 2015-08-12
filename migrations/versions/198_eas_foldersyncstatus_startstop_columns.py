"""eas foldersyncstatus startstop columns

Revision ID: 301d22aa96b8
Revises: 3cf51fb0e76a
Create Date: 2015-08-12 10:16:11.628828

"""

# revision identifiers, used by Alembic.
revision = '301d22aa96b8'
down_revision = '3cf51fb0e76a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easfoldersyncstatus'):
        return
    op.add_column('easfoldersyncstatus', sa.Column('initial_sync_end',
                                                   sa.DateTime(),
                                                   nullable=True))
    op.add_column('easfoldersyncstatus', sa.Column('initial_sync_start',
                                                   sa.DateTime(),
                                                   nullable=True))


def downgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easfoldersyncstatus'):
        return
    op.drop_column('easfoldersyncstatus', 'initial_sync_start')
    op.drop_column('easfoldersyncstatus', 'initial_sync_end')
