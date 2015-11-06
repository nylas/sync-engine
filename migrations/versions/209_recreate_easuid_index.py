"""Re-create EASUid index.

Revision ID: 3618838f5bc6
Revises: 1962d17d1c0a
Create Date: 2015-11-06 00:35:50.859321

"""

# revision identifiers, used by Alembic.
revision = '3618838f5bc6'
down_revision = '1962d17d1c0a'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    if not conn.engine.has_table('easuid'):
        return
    conn.execute(text('set @@lock_wait_timeout = 20;'))
    conn.execute(text('set @@foreign_key_checks = 0;'))
    op.create_index(u'ix_easaccount_id_2', 'easuid',
                    ['easaccount_id', 'device_id', 'easfoldersyncstatus_id',
                     'server_id'])


def downgrade():
    pass
