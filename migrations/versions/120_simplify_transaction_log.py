"""simplify transaction log

Revision ID: 8c2406df6f8
Revises:58732bb5d14b
Create Date: 2014-08-08 01:57:17.144405

"""

# revision identifiers, used by Alembic.
revision = '8c2406df6f8'
down_revision = '58732bb5d14b'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text('''
        ALTER TABLE transaction
            CHANGE public_snapshot snapshot LONGTEXT,
            CHANGE table_name object_type VARCHAR(20),
            DROP COLUMN private_snapshot,
            DROP COLUMN delta,
            ADD INDEX `ix_transaction_object_public_id` (`object_public_id`)
        '''))


def downgrade():
    raise Exception()
