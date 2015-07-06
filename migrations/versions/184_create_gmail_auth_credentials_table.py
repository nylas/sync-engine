"""create gmail account to refresh token id table

Revision ID: 2ac4e3c4e049
Revises: 3a58d466f61d
Create Date: 2015-06-30 21:21:56.843813

"""

# revision identifiers, used by Alembic.
revision = '2ac4e3c4e049'
down_revision = '3a58d466f61d'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.create_table(
        'gmailauthcredentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('gmailaccount_id', sa.Integer(), nullable=False),
        sa.Column('refresh_token_id', sa.Integer(), nullable=False),
        sa.Column('scopes', mysql.VARCHAR(length=512), nullable=False),
        sa.Column('g_id_token', mysql.VARCHAR(length=1024), nullable=False),
        sa.Column('client_id', mysql.VARCHAR(length=256), nullable=False),
        sa.Column('client_secret', mysql.VARCHAR(length=256)),
        sa.Column('is_valid', sa.Boolean(),
                  nullable=False, server_default=sa.sql.expression.true()),
        sa.ForeignKeyConstraint(
            ['gmailaccount_id'], [u'gmailaccount.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['refresh_token_id'], [u'secret.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', 'gmailaccount_id', 'refresh_token_id'),
        sa.UniqueConstraint('refresh_token_id'),
    )


def downgrade():
    op.drop_table('gmailauthcredentials')
