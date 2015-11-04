"""Drop EASUid UniqueConstraint

Revision ID: 1962d17d1c0a
Revises: 4b225df49747
Create Date: 2015-11-04 23:11:43.661200

"""

# revision identifiers, used by Alembic.
revision = '1962d17d1c0a'
down_revision = '4b225df49747'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    if not conn.engine.has_table('easuid'):
        return
    conn.execute(text('set @@lock_wait_timeout = 20;'))
    conn.execute(text('set @@foreign_key_checks = 0;'))
    op.drop_constraint(u'easaccount_id_2', 'easuid', type_='unique')


def downgrade():
    pass
