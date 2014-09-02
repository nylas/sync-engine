"""relationship between parts and messages is M2M now

Revision ID: 2b89164aa9cd
Revises: 4e3e8abea884
Create Date: 2014-08-27 16:12:06.828258

"""

# revision identifiers, used by Alembic.
revision = '2b89164aa9cd'
down_revision = '24e9afe91349'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.create_table('messagepartassociation',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], [u'message.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['part_id'], [u'part.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', 'message_id', 'part_id')
    )

    op.create_index("op.f('ix_messagepartassociation_created_at')",
                    'messagepartassociation', ['created_at'], unique=False)
    op.create_index("op.f('ix_messagepartassociation_deleted_at')",
                    'messagepartassociation', ['deleted_at'], unique=False)
    op.create_index("op.f('ix_messagepartassociation_updated_at')",
                    'messagepartassociation', ['updated_at'], unique=False)

    op.drop_constraint(u'part_ibfk_2', 'part', type_='foreignkey')
    op.drop_index('message_id', table_name='part')
    op.drop_constraint(u'message_id', 'part', type_='unique')
    conn = op.get_bind()
    conn.execute(text(("INSERT INTO messagepartassociation "
                       "(created_at, updated_at, deleted_at,"
                       "message_id, part_id)"
                       "SELECT NOW(), NOW(), NULL, message_id,"
                       " id FROM part WHERE message_id IS NOT NULL;")))
    op.drop_column(u'part', 'message_id')


def downgrade():
    # It doesn't make sense to have a downgrade path since
    # we'd destroy information.
    raise NotImplementedError
