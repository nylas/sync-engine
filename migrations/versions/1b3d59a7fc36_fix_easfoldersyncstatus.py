"""fix easfoldersyncstatus

Revision ID: 1b3d59a7fc36
Revises: 16bfe5547545
Create Date: 2015-02-24 01:15:03.395747

"""

# revision identifiers, used by Alembic.
revision = '1b3d59a7fc36'
down_revision = '16bfe5547545'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()

    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE easfoldersyncstatus DROP FOREIGN KEY `easfoldersyncstatus_ibfk_1`"))
    conn.execute(text("ALTER TABLE easfoldersyncstatus ADD CONSTRAINT `easfoldersyncstatus_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `easaccount` (`id`) ON DELETE CASCADE"))

    conn.execute(text("ALTER TABLE easfoldersyncstatus DROP FOREIGN KEY `easfoldersyncstatus_ibfk_2`"))

    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))

def downgrade():
    conn = op.get_bind()

    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))

    conn.execute(text("ALTER TABLE easfoldersyncstatus DROP FOREIGN KEY `easfoldersyncstatus_ibfk_1`"))
    conn.execute(text("ALTER TABLE easfoldersyncstatus ADD CONSTRAINT `easfoldersyncstatus_ibfk_1` FOREIGN KEY (`account_id`) REFERENCES `easaccount` (`id`)"))

    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
