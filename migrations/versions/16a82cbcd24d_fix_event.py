"""fix event

Revision ID: 16a82cbcd24d
Revises: 181cab41ffa7
Create Date: 2015-02-20 23:33:04.552701

"""

# revision identifiers, used by Alembic.
revision = '16a82cbcd24d'
down_revision = '181cab41ffa7'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    # Technically we should also update the charset to be strict ascii but this is
    # a very costly operation.
    conn.execute(text("ALTER TABLE event MODIFY uid varchar(767) NOT NULL"))
    conn.execute(text("ALTER TABLE event MODIFY created_at DATETIME NOT NULL"))
    conn.execute(text("ALTER TABLE event MODIFY updated_at DATETIME NOT NULL"))
    conn.execute(text("ALTER TABLE event MODIFY namespace_id int(11) NOT NULL"))

    # Changing varchar length from one byte to two byte is an expensive operations which
    # requires a table copy
    # conn.execute(text("ALTER TABLE event MODIFY owner varchar(1024)"))
    conn.execute(text("ALTER TABLE event DROP FOREIGN KEY `event_ibfk_3`"))
    conn.execute(text("ALTER TABLE event ADD CONSTRAINT `event_ibfk_3` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))

def downgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE event MODIFY uid varchar(767)"))
    conn.execute(text("ALTER TABLE event MODIFY created_at DATETIME"))
    conn.execute(text("ALTER TABLE event MODIFY updated_at DATETIME"))
    conn.execute(text("ALTER TABLE event MODIFY namespace_id int(11)"))
    # conn.execute(text("ALTER TABLE event MODIFY owner varchar(255)"))
    conn.execute(text("ALTER TABLE event DROP FOREIGN KEY `event_ibfk_3`"))
    conn.execute(text("ALTER TABLE event ADD CONSTRAINT `event_ibfk_3` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`)"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
