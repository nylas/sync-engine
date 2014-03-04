"""rename message_id to message_id_header

Revision ID: 217431caacc7
Revises: 2605b23e1fe6
Create Date: 2014-03-04 06:51:13.008195

"""

# revision identifiers, used by Alembic.
revision = '217431caacc7'
down_revision = '2605b23e1fe6'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("ALTER TABLE message CHANGE message_id message_id_header VARCHAR(255) NULL")


def downgrade():
    # First make all current NULL values actually 0. This isn't a great solution, but it works.
    print "WARNING: This removes data about messages that do not contain a Message-Id header!"
    op.execute("UPDATE message SET message_id_header=0 WHERE message_id_header IS NULL")
    op.execute("ALTER TABLE message CHANGE message_id_header message_id VARCHAR(255) NOT NULL")

