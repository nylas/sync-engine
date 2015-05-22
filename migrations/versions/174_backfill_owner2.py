"""backfill owner column data

Revision ID: 4ef055945390
Revises: fd32a69381a
Create Date: 2015-05-13 14:04:12.304013

"""

# revision identifiers, used by Alembic.
revision = '4ef055945390'
down_revision = 'fd32a69381a'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))

    print "Copying data."
    conn.execute(text("UPDATE event set owner2 = owner where owner2 IS NULL"))


def downgrade():
    raise Exception("Can't undo an UPDATE")
