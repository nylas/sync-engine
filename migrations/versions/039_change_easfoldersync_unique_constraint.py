"""Change EASFolderSync unique constraint

Revision ID: 1c72d8a0120e
Revises: 1edbd63582c2
Create Date: 2014-06-12 22:44:31.934659

"""

# revision identifiers, used by Alembic.
revision = '1c72d8a0120e'
down_revision = '1edbd63582c2'

from alembic import op
from sqlalchemy.ext.declarative import declarative_base


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    if 'easfoldersync' in Base.metadata.tables:
        op.create_unique_constraint('uq_account_id_eas_folder_id',
                                    'easfoldersync',
                                    ['account_id', 'eas_folder_id'])
        op.drop_constraint('account_id', 'easfoldersync', type_='unique')


def downgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    if 'easfoldersync' in Base.metadata.tables:
        op.create_unique_constraint('account_id',
                                    'easfoldersync',
                                    ['account_id', 'folder_name'])
        op.drop_constraint('uq_account_id_eas_folder_id', 'easfoldersync',
                           type_='unique')
