"""remove erroneous soft-deleted imapuids

We are no longer using soft deletes on this table. All soft-deleted uids
should be hard-deleted instead.

Revision ID: 146b1817e4a8
Revises: 59b42d0ac749
Create Date: 2014-05-09 22:16:00.387937

"""

# revision identifiers, used by Alembic.
revision = '924ffd092832'
down_revision = '146b1817e4a8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


def upgrade():
    t = table('imapuid', column('deleted_at', sa.DateTime()))

    op.execute(t.delete().where(t.c.deleted_at != None))


def downgrade():
    # this was fixing a mistake
    pass
