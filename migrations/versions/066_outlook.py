"""outlook

Revision ID: 1ceff61ec112
Revises: 2e6120c97485
Create Date: 2014-07-22 10:17:33.115621

"""

# revision identifiers, used by Alembic.
revision = '1ceff61ec112'
down_revision = '2e6120c97485'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('outlookaccount',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['id'], [u'imapaccount.id'],
                                            ondelete='CASCADE'),
                    sa.Column('refresh_token_id',
                              sa.Integer(), nullable=True),
                    sa.Column('scope', sa.String(length=512), nullable=True),
                    sa.Column('locale', sa.String(length=8), nullable=True),
                    sa.Column('client_id', sa.String(length=256),
                              nullable=True),
                    sa.Column('client_secret', sa.String(length=256),
                              nullable=True),
                    sa.Column('o_id', sa.String(length=32), nullable=True),
                    sa.Column('o_id_token', sa.String(length=1024),
                              nullable=True),
                    sa.Column('link', sa.String(length=256), nullable=True),
                    sa.Column('name', sa.String(length=256), nullable=True),
                    sa.Column('gender', sa.String(length=16), nullable=True),
                    sa.Column('family_name', sa.String(length=256),
                              nullable=True),
                    sa.Column('given_name', sa.String(length=256),
                              nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.alter_column('secret', 'secret', type_=sa.String(length=2048))


def downgrade():
    op.drop_table('outlookaccount')
