"""update_google_calendar_uids

Revision ID: c77a90d524
Revises: 557378226d9f
Create Date: 2015-03-12 17:58:50.477526

"""

# revision identifiers, used by Alembic.
revision = 'c77a90d524'
down_revision = '557378226d9f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    conn = op.get_bind()
    conn.execute(
        '''UPDATE calendar JOIN namespace ON calendar.namespace_id=namespace.id
           JOIN gmailaccount ON namespace.account_id=gmailaccount.id SET
           calendar.uid=calendar.name''')


def downgrade():
    raise Exception
