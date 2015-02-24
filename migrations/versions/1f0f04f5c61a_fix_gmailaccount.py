"""fix gmailaccount

Revision ID: 1f0f04f5c61a
Revises: 458da6f0704f
Create Date: 2015-02-24 01:38:37.066037

"""

# revision identifiers, used by Alembic.
revision = '1f0f04f5c61a'
down_revision = '458da6f0704f'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE gmailaccount MODIFY refresh_token_id int(11) NOT NULL"))

def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE gmailaccount MODIFY refresh_token_id int(11)"))
