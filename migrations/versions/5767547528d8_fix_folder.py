"""fix folder

Revision ID: 5767547528d8
Revises: 16a82cbcd24d
Create Date: 2015-02-23 17:09:13.950746

"""

# revision identifiers, used by Alembic.
revision = '5767547528d8'
down_revision = '16a82cbcd24d'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE folder DROP FOREIGN KEY `folder_fk1`"))
    conn.execute(text("ALTER TABLE folder ADD CONSTRAINT `folder_fk1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`) ON DELETE CASCADE"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE folder DROP FOREIGN KEY `folder_fk1`"))
    conn.execute(text("ALTER TABLE folder ADD CONSTRAINT `folder_fk1` FOREIGN KEY (`account_id`) REFERENCES `account` (`id`)"))
