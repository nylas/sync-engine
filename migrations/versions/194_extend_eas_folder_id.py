"""extend size of eas_folder_id and eas_parent_id

Revision ID: 211e93aff1e1
Revises: 2493281d621
Create Date: 2015-03-20 18:50:29.961734

"""

# revision identifiers, used by Alembic.
revision = '69e93aef3e9'
down_revision = '691fa97024d'

from alembic import op
from sqlalchemy.sql import text
from sqlalchemy.ext.declarative import declarative_base


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))

    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    if 'easfoldersyncstatus' in Base.metadata.tables:
        conn.execute(text("ALTER TABLE easfoldersyncstatus MODIFY eas_folder_id VARCHAR(191),"
                          "                                MODIFY eas_parent_id VARCHAR(191)"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))

    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    if 'easfoldersyncstatus' in Base.metadata.tables:
        conn.execute(text("ALTER TABLE easfoldersyncstatus MODIFY eas_folder_id VARCHAR(64),"
                          "                                MODIFY eas_parent_id VARCHAR(64)"))
