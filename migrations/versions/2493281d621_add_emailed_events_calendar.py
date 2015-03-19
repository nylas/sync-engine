"""add emailed events calendar

Revision ID: 2493281d621
Revises: 54dcea22a268
Create Date: 2015-03-17 00:41:28.987168

"""

# revision identifiers, used by Alembic.
revision = '2493281d621'
down_revision = '54dcea22a268'

from alembic import op
from sqlalchemy.sql import text
import sqlalchemy as sa


def upgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE account DROP FOREIGN KEY account_ibfk_10"))
    # Orphan all the default calendars. We need to do it because we are going to
    # replace them with "Email events" calendars.
    conn.execute(text("UPDATE account SET default_calendar_id = NULL"))
    conn.execute(text("ALTER TABLE account CHANGE default_calendar_id emailed_events_calendar_id INTEGER"))
    conn.execute(text("ALTER TABLE account ADD CONSTRAINT emailed_events_fk "
                      "FOREIGN KEY (emailed_events_calendar_id) REFERENCES "
                      "calendar(id) ON DELETE SET NULL"))

def downgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE account DROP FOREIGN KEY emailed_events_fk"))
    conn.execute(text("ALTER TABLE account CHANGE COLUMN emailed_events_calendar_id default_calendar_id INTEGER"))
    conn.execute(text("ALTER TABLE account ADD CONSTRAINT account_ibfk_10 "
                      "FOREIGN KEY (default_calendar_id) REFERENCES "
                      "calendar(id) ON DELETE SET NULL"))
