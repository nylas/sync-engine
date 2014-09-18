"""secrets_endgame

Revision ID: 248ec24a39f
Revises: 38c29430efeb
Create Date: 2014-09-18 03:03:52.580809

"""

# revision identifiers, used by Alembic.
revision = '248ec24a39f'
down_revision = '38c29430efeb'

from alembic import op


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine()
    if engine.has_table('easaccount'):
        op.drop_column('easaccount', 'password')
    op.drop_column('secret', 'secret')


def downgrade():
    raise Exception()
