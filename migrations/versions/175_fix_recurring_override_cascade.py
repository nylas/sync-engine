"""fix recurring override cascade

Revision ID: 6e5b154d917
Revises: 41f957b595fc
Create Date: 2015-05-25 16:23:40.563050

"""

# revision identifiers, used by Alembic.
revision = '6e5b154d917'
down_revision = '4ef055945390'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    # Check this migration is needed
    fk_name, fk_delete = conn.execute(
        '''SELECT constraint_name, delete_rule FROM
           information_schema.referential_constraints WHERE
           constraint_schema=DATABASE() AND
           table_name='recurringeventoverride' AND
           constraint_name='recurringeventoverride_ibfk_2'
           ''').fetchone()

    if fk_delete == 'CASCADE':
        print 'Checked fk: {}. This migration is not needed, skipping.'.format(fk_name)
        return

    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE recurringeventoverride DROP FOREIGN KEY "
                      "`recurringeventoverride_ibfk_2`"))
    conn.execute(text("ALTER TABLE recurringeventoverride ADD CONSTRAINT recurringeventoverride_ibfk_2"
                      " FOREIGN KEY (`master_event_id`) REFERENCES `event` (`id`) ON DELETE CASCADE"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE recurringeventoverride DROP FOREIGN KEY "
                      "`recurringeventoverride_ibfk_2`"))
    conn.execute(text("ALTER TABLE recurringeventoverride ADD CONSTRAINT recurringeventoverride_ibfk_2"
                      " FOREIGN KEY (`master_event_id`) REFERENCES `event` (`id`)"))
