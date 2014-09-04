"""relationship between blocks and parts is 1-to-many

Revision ID: 2b89164aa9cd
Revises: 4e3e8abea884
Create Date: 2014-08-27 16:12:06.828258

"""

# revision identifiers, used by Alembic.
revision = '2b89164aa9cd'
down_revision = '24e9afe91349'

from datetime import datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


def upgrade():
    table_name = 'part'

    # Create a new block_id table to make parts be relational
    op.add_column(table_name, sa.Column('block_id',
                  sa.Integer, nullable=True))

    # Add audit timestamps as Parts will no longer inherit from blocks
    op.add_column(table_name, sa.Column('created_at', sa.DateTime,
                                        nullable=True))
    op.add_column(table_name, sa.Column('updated_at', sa.DateTime,
                                        nullable=True))
    op.add_column(table_name, sa.Column('deleted_at', sa.DateTime,
                                        nullable=True))

    # Create a migration table
    parts = table(table_name,
                  column('id', sa.Integer),
                  column('block_id', sa.Integer),
                  column('created_at', sa.DateTime),
                  column('updated_at', sa.DateTime))

    # Copy the old id to the block_id column
    s = parts.update().values(block_id=parts.c['id'],
                              created_at=datetime.utcnow(),
                              updated_at=datetime.utcnow())
    conn = op.get_bind()
    conn.execute(s)

    # Drop the old foreign key constraint for part.id == block.id
    op.drop_constraint('part_ibfk_1', table_name, type_='foreignkey')

    # new constraint part.block_id == block.id
    op.create_foreign_key('part_ibfk_1', table_name, 'block',
                          ['block_id'], ['id'])

    # make part.block_id non-nullable now that they've been set
    op.alter_column(table_name, 'block_id',
                    nullable=False,
                    existing_nullable=True,
                    existing_type=sa.Integer)

    op.alter_column(table_name, 'created_at', existing_type=sa.DateTime,
                    existing_nullable=True,
                    nullable=False)

    op.alter_column(table_name, 'updated_at', existing_type=sa.DateTime,
                    existing_nullable=True,
                    nullable=False)

    op.alter_column(table_name, 'id', existing_type=sa.Integer,
                    autoincrement=True)


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
