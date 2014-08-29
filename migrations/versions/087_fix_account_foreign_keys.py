"""fix account foreign keys

Revision ID: 565c7325c51d
Revises: 1ac03cab7a24
Create Date: 2014-08-29 20:24:38.952595

"""

# revision identifiers, used by Alembic.
revision = '565c7325c51d'
down_revision = '1ac03cab7a24'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    inspector = sa.inspect(engine)
    if 'default_calendar_ibfk_1' in [k['name'] for k in
                                     inspector.get_foreign_keys('account')]:
        op.drop_constraint('default_calendar_ibfk_1', 'account',
                           type_='foreignkey')
        op.create_foreign_key('account_ibfk_10', 'account', 'calendar',
                              ['default_calendar_id'], ['id'])


def downgrade():
    raise Exception('No rolling back')
