"""relax_participants_by_email_constraint

Revision ID: 3f01a3f1b4cc
Revises: 5305d4ae30b4
Create Date: 2015-02-19 00:06:07.906794

"""

# revision identifiers, used by Alembic.
revision = '3f01a3f1b4cc'
down_revision = '5305d4ae30b4'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()

    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE event MODIFY participants_by_email TEXT;"))
    conn.execute(text("ALTER TABLE event DROP FOREIGN KEY `event_ibfk_2`"))
    conn.execute(text("ALTER TABLE event ADD CONSTRAINT `event_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE event DROP FOREIGN KEY `event_ibfk_2`"))
    conn.execute(text("ALTER TABLE event ADD CONSTRAINT `event_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`)"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
