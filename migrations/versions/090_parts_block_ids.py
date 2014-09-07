"""relationship between blocks and parts is 1-to-many

Revision ID: 2b89164aa9cd
Revises: 4e3e8abea884
Create Date: 2014-08-27 16:12:06.828258

"""

# revision identifiers, used by Alembic.
revision = '2b89164aa9cd'
down_revision = '2c577a8a01b7'

from datetime import datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    # Create a new block_id table to make parts be relational
    # Add audit timestamps as Parts will no longer inherit from blocks
    conn.execute(text("""
        ALTER TABLE part
            ADD COLUMN block_id INTEGER,
            ADD COLUMN created_at DATETIME,
            ADD COLUMN updated_at DATETIME,
            ADD COLUMN deleted_at DATETIME
        """))

    conn.execute(text(
        "UPDATE part SET block_id=part.id, created_at=:now, updated_at=:now"),
        now=datetime.utcnow())

    conn.execute(text("""
        ALTER TABLE part
            DROP FOREIGN KEY part_ibfk_1,
            MODIFY block_id INTEGER NOT NULL,
            MODIFY created_at DATETIME NOT NULL,
            MODIFY updated_at DATETIME NOT NULL,
            MODIFY id INTEGER NULL AUTO_INCREMENT
        """))

    # can't batch this with other alterations while maintaining foreig key name
    op.create_foreign_key('part_ibfk_1', 'part', 'block', ['block_id'], ['id'])


def downgrade():
    table_name = 'part'
    op.drop_constraint('part_ibfk_1', table_name,
                       type_='foreignkey')
    op.drop_column(table_name, 'block_id')
    op.create_foreign_key('part_ibfk_1', table_name, 'block',
                          ['id'], ['id'])
    op.drop_column(table_name, 'created_at')
    op.drop_column(table_name, 'deleted_at')
    op.drop_column(table_name, 'updated_at')
    op.alter_column(table_name, 'id', existing_type=sa.Integer,
                    autoincrement=False)
