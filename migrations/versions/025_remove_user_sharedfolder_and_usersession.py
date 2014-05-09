"""Remove User, SharedFolder, and UserSession

Revision ID: 59b42d0ac749
Revises: 4c1eb89f6bed
Create Date: 2014-05-09 07:47:54.866524

"""

# revision identifiers, used by Alembic.
revision = '59b42d0ac749'
down_revision = '4c1eb89f6bed'

from alembic import op


def upgrade():
    op.drop_constraint('account_ibfk_1', 'account', type_='foreignkey')
    op.drop_constraint('usersession_ibfk_1', 'usersession', type_='foreignkey')
    op.drop_constraint(
        'sharedfolder_ibfk_1', 'sharedfolder', type_='foreignkey')
    op.drop_constraint(
        'sharedfolder_ibfk_2', 'sharedfolder', type_='foreignkey')

    op.drop_table(u'user')
    op.drop_table(u'sharedfolder')
    op.drop_table(u'usersession')
    op.drop_column('account', u'user_id')


def downgrade():
    raise Exception("Not supported! You didn't need those tables anyway.")
