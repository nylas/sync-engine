"""fix contact

Revision ID: 181cab41ffa7
Revises: 2192f61f60d5
Create Date: 2015-02-20 23:22:01.558007

"""

# revision identifiers, used by Alembic.
revision = '181cab41ffa7'
down_revision = '2192f61f60d5'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE contact DROP FOREIGN KEY `contact_ibfk_2`"))
    conn.execute(text("ALTER TABLE contact ADD CONSTRAINT `contact_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE contact DROP FOREIGN KEY `contact_ibfk_2`"))
    conn.execute(text("ALTER TABLE contact ADD CONSTRAINT `contact_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
