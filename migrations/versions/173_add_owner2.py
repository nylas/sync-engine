"""fix owner column length --- it's a varchar(255) on our prod db
when it should be a varchar(1024)

Revision ID: fd32a69381a
Revises: 365071c47fa7
Create Date: 2015-05-11 11:47:01.710610

"""

# revision identifiers, used by Alembic.
revision = 'fd32a69381a'
down_revision = 'd0427f9f3d1'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE event "
                      "ADD COLUMN owner2 varchar(1024) DEFAULT NULL"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE event DROP COLUMN owner2"))
