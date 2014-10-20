"""Fix EASUid delete cascades

Revision ID: 420bf3422c4f
Revises: 10ecf4841ac3
Create Date: 2014-10-23 11:02:58.010469

"""

# revision identifiers, used by Alembic.
revision = '420bf3422c4f'
down_revision = '10ecf4841ac3'

from alembic import op


def upgrade():
    op.drop_constraint('easuid_ibfk_2', 'easuid', type_='foreignkey')
    op.create_foreign_key('easuid_ibfk_2', 'easuid', 'message',
                          ['message_id'], ['id'], ondelete='cascade')

    op.drop_constraint('easuid_ibfk_3', 'easuid', type_='foreignkey')
    op.create_foreign_key('easuid_ibfk_3', 'easuid', 'folder',
                          ['folder_id'], ['id'], ondelete='cascade')


def downgrade():
    raise Exception('Nope.')
