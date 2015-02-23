"""fix message

Revision ID: 3414e42956c9
Revises: 3148ccd8cc9b
Create Date: 2015-02-23 17:37:59.354724

"""

# revision identifiers, used by Alembic.
revision = '3414e42956c9'
down_revision = '3148ccd8cc9b'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE message DROP FOREIGN KEY `message_ibfk_3`"))
    conn.execute(text("ALTER TABLE message ADD CONSTRAINT `message_ibfk_3` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE"))



def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE message DROP FOREIGN KEY `message_ibfk_3`"))
    conn.execute(text("ALTER TABLE message ADD CONSTRAINT `message_ibfk_3` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`)"))
