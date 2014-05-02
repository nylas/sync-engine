"""Add search tokens.

Revision ID: 482338e7a7d6
Revises: 41a7e825d108
Create Date: 2014-03-18 00:16:49.525732

"""

# revision identifiers, used by Alembic.
revision = '482338e7a7d6'
down_revision = 'adc646e1f11'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'searchtoken',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=True),
        sa.Column('source', sa.Enum('name', 'email_address'), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('searchtoken')
