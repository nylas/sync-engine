"""fix_calendar_defaults

Revision ID: 2192f61f60d5
Revises: 1bbf7ca27d8b
Create Date: 2015-02-18 19:37:44.107084

"""

# revision identifiers, used by Alembic.
revision = '2192f61f60d5'
down_revision = '1bbf7ca27d8b'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()

    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    #conn.execute(text("ALTER TABLE calendar MODIFY namespace_id int(11) NOT NULL;"))
    #conn.execute(text("ALTER TABLE calendar MODIFY created_at DATETIME NOT NULL;"))
    ## changing charset requires copying the whole table
    # conn.execute(text("ALTER TABLE calendar MODIFY uid varchar(767) CHARACTER SET ASCII NOT NULL;"))
    # conn.execute(text("ALTER TABLE calendar MODIFY provider_name varchar(128);"))
    conn.execute(text("ALTER TABLE calendar DROP FOREIGN KEY `calendar_ibfk_2`"))
    conn.execute(text("ALTER TABLE calendar ADD CONSTRAINT `calendar_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))

def downgrade():
    conn = op.get_bind()

    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    #conn.execute(text("ALTER TABLE calendar MODIFY namespace_id int(11);"))
    #conn.execute(text("ALTER TABLE calendar MODIFY created_at DATETIME;"))
    # conn.execute(text("ALTER TABLE calendar MODIFY uid varchar(767);"))
    #conn.execute(text("ALTER TABLE calendar MODIFY provider_name varchar(64);"))
    conn.execute(text("ALTER TABLE calendar DROP FOREIGN KEY `calendar_ibfk_2`"))
    conn.execute(text("ALTER TABLE calendar ADD CONSTRAINT `calendar_ibfk_2` FOREIGN KEY (`namespace_id`) REFERENCES `namespace` (`id`)"))

    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
