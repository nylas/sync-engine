"""Remove notion of 'remote' contact and drop contact 'source' column

Revision ID: 3ab34bc85c8d
Revises: 3f01a3f1b4cc
Create Date: 2015-02-16 16:03:45.288539

"""

# revision identifiers, used by Alembic.
revision = '3ab34bc85c8d'
down_revision = '3f01a3f1b4cc'

from alembic import op
from sqlalchemy.ext.declarative import declarative_base


def upgrade():
    from inbox.models.session import session_scope
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Contact_Old(Base):
        __table__ = Base.metadata.tables['contact']

    # Delete the "remote" contacts. This is just a server cache for comparing
    # any changes, now handled by the previous "local" contacts
    with session_scope() as db_session:
        db_session.query(Contact_Old).filter_by(source='remote').delete()

    op.drop_column('contact', 'source')


def downgrade():
    raise Exception("Can't roll back. Migration removed data.")
