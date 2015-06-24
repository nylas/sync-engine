"""migrate event descriptions

Revision ID: ea9dc8742ee
Revises: 56500282e024
Create Date: 2015-06-23 18:09:33.804125

"""

# revision identifiers, used by Alembic.
revision = 'ea9dc8742ee'
down_revision = '56500282e024'

from alembic import op


def upgrade():
    conn = op.get_bind()
    while True:
        res = conn.execute(
            'UPDATE event SET _description=description '
            'WHERE _description IS NULL LIMIT 100000')
        print 'Updated {} rows'.format(res.rowcount)
        if res.rowcount == 0:
            return


def downgrade():
    pass
