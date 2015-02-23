"""fix tagitem

Revision ID: 16bfe5547545
Revises: 49024c586df0
Create Date: 2015-02-23 17:50:31.132453

"""

# revision identifiers, used by Alembic.
revision = '16bfe5547545'
down_revision = '49024c586df0'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE tagitem DROP FOREIGN KEY `tagitem_ibfk_1`"))
    conn.execute(text("ALTER TABLE tagitem ADD CONSTRAINT `tagitem_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`) ON DELETE CASCADE"))
    conn.execute(text("ALTER TABLE tagitem DROP FOREIGN KEY `tagitem_ibfk_2`"))
    conn.execute(text("ALTER TABLE tagitem ADD CONSTRAINT `tagitem_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`id`) ON DELETE CASCADE"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE tagitem DROP FOREIGN KEY `tagitem_ibfk_1`"))
    conn.execute(text("ALTER TABLE tagitem ADD CONSTRAINT `tagitem_ibfk_1` FOREIGN KEY (`thread_id`) REFERENCES `thread` (`id`)"))
    conn.execute(text("ALTER TABLE tagitem DROP FOREIGN KEY `tagitem_ibfk_2`"))
    conn.execute(text("ALTER TABLE tagitem ADD CONSTRAINT `tagitem_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`id`)"))
