"""add account.name column

Revision ID: 22d076f48b88
Revises: 4011b943a24d
Create Date: 2014-10-14 18:40:50.160707

"""

# revision identifiers, used by Alembic.
revision = '22d076f48b88'
down_revision = '4011b943a24d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('account', sa.Column('name', sa.String(length=256),
                                       server_default='', nullable=False))
    conn = op.get_bind()
    conn.execute('''
        UPDATE account JOIN gmailaccount ON account.id=gmailaccount.id
        SET account.name=gmailaccount.name''')
    conn.execute('''
        UPDATE account JOIN outlookaccount ON account.id=outlookaccount.id
        SET account.name=outlookaccount.name''')
    op.drop_column('gmailaccount', 'name')
    op.drop_column('outlookaccount', 'name')


def downgrade():
    raise Exception()
