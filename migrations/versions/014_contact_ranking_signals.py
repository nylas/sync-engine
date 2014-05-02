"""contact ranking signals

Revision ID: 563d405d1f99
Revises: 169cac0cd87e
Create Date: 2014-04-17 19:32:37.715207

"""

# revision identifiers, used by Alembic.
revision = '563d405d1f99'
down_revision = 'f7dbd9bf4a6'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'searchsignal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=40), nullable=True),
        sa.Column('value', sa.Integer(), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column('contact', sa.Column('score', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('contact', 'score')
    op.drop_table('searchsignal')
