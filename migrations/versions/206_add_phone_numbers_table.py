"""create phone number table

Revision ID: 2ac4e3c4e049
Revises: 3a58d466f61d
Create Date: 2015-06-30 21:21:56.843813

"""

# revision identifiers, used by Alembic.
revision = 'gu8eqpm6f2x1n0fg'
down_revision = '302d9f6b22f3'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.create_table(
        'phonenumber',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('type', mysql.VARCHAR(length=64), nullable=True),
        sa.Column('number', mysql.VARCHAR(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ['contact_id'], [u'contact.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_phonenumber_created_at',
                    'phonenumber', ['created_at'], unique=False)
    op.create_index('ix_phonenumber_updated_at',
                    'phonenumber', ['updated_at'], unique=False)
    op.create_index('ix_phonenumber_contact_id',
                    'phonenumber', ['contact_id'], unique=False)
    op.create_index('ix_phonenumber_deleted_at',
                    'phonenumber', ['deleted_at'], unique=False)


def downgrade():
    op.drop_table('phonenumber')
