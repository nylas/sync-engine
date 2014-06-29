"""multiple contact providers

Revision ID: 169cac0cd87e
Revises: 3c11391b5eb0
Create Date: 2014-03-28 19:16:15.450474

"""

# revision identifiers, used by Alembic.
revision = '169cac0cd87e'
down_revision = '3c11391b5eb0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('contact', sa.Column('provider_name', sa.String(length=64),
                                       nullable=False))
    op.alter_column('contact', 'g_id', new_column_name='uid', nullable=False,
                    existing_type=sa.String(length=64))
    # Previously we were just syncing google contacts.
    op.execute('UPDATE contact SET provider_name="google"')
    op.drop_constraint('g_id', 'contact', type_='unique')
    op.create_unique_constraint('uid', 'contact', ['uid', 'source',
                                                   'account_id',
                                                   'provider_name'])


def downgrade():
    op.alter_column('contact', 'uid', new_column_name='g_id',
                    existing_type=sa.String(length=64), existing_nullable=True)
    op.drop_column('contact', 'provider_name')
    op.drop_constraint('uid', 'contact', type_='unique')
    op.create_unique_constraint('g_id', 'contact', ['g_id', 'source',
                                                    'account_id'])
