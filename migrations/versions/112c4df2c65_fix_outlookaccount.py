"""fix outlookaccount

Revision ID: 112c4df2c65
Revises: 3414e42956c9
Create Date: 2015-02-23 17:44:39.299142

"""

# revision identifiers, used by Alembic.
revision = '112c4df2c65'
down_revision = '3414e42956c9'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE outlookaccount MODIFY refresh_token_id int(11) NOT NULL"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE outlookaccount MODIFY refresh_token_id int(11) DEFAULT NULL"))
