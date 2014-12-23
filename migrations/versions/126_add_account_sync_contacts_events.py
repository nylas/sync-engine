"""Add the [_]sync_{contacts|events} cols to the Account tbl.

Revision ID: 262436681c4
Revises: 955792afd00
Create Date: 2014-12-19 13:33:19.653113

"""

# revision identifiers, used by Alembic.
revision = '262436681c4'
down_revision = '955792afd00'


from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('account', sa.Column('sync_contacts',
                                       sa.Boolean,
                                       nullable=False,
                                       default=False))
    op.add_column('account', sa.Column('sync_events',
                                       sa.Boolean,
                                       nullable=False,
                                       default=False))
    connection = op.get_bind()
    connection.execute(
        sa.sql.text(
            '''
            update account join gmailaccount on account.id = gmailaccount.id
            set account.sync_contacts = 1
            where gmailaccount.scope like "%https://www.google.com/m8/feeds%"
            '''
        )
    )
    connection.execute(
        sa.sql.text(
            '''
            update account join gmailaccount on account.id = gmailaccount.id
            set account.sync_events = 1
            where gmailaccount.scope
            like "%https://www.googleapis.com/auth/calendar%"
            '''
        )
    )


def downgrade():
    op.drop_column('account', 'sync_contacts')
    op.drop_column('account', 'sync_events')
