"""remove easeventuid

Revision ID: 581e91bd7141
Revises: 262436681c4
Create Date: 2015-01-10 00:57:50.944460

"""

# revision identifiers, used by Alembic.
revision = '581e91bd7141'
down_revision = '262436681c4'

from alembic import op


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine()

    if not engine.has_table('easeventuid'):
        return

    op.drop_constraint('easeventuid_ibfk_1', 'easeventuid', type_='foreignkey')
    op.drop_constraint('easeventuid_ibfk_2', 'easeventuid', type_='foreignkey')
    op.drop_constraint('easeventuid_ibfk_3', 'easeventuid', type_='foreignkey')

    op.drop_table('easeventuid')


def downgrade():
    raise Exception('No going back.')
