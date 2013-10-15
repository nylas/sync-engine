"""Index users by email.

Revision ID: 1d7229c6b257
Revises: 5a384f700423
Create Date: 2013-09-26 12:32:10.907886

"""

# revision identifiers, used by Alembic.
revision = '1d7229c6b257'
down_revision = '5a384f700423'

from alembic import op

def upgrade():
    op.create_index('users_by_email', 'users', ['g_email'])

def downgrade():
    op.drop_index('users_by_email', 'users')
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
