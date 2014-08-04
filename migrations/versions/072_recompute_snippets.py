"""recompute snippets

Revision ID: 4e93522b5b62
Revises: 2525c5245cc2
Create Date: 2014-07-31 09:37:48.099402

"""

# revision identifiers, used by Alembic.
revision = '4e93522b5b62'
down_revision = '3bb5d61c895c'

from inbox.ignition import main_engine
from inbox.models.session import session_scope
from inbox.models.message import Message
from sqlalchemy.ext.declarative import declarative_base


engine = main_engine()
Base = declarative_base()
Base.metadata.reflect(engine)


# solution from http://stackoverflow.com/a/1217947
def page_query(q):
    CHUNK_SIZE = 1000
    offset = 0
    while True:
        r = False
        for elem in q.limit(CHUNK_SIZE).offset(offset):
            r = True
            yield elem
        offset += CHUNK_SIZE
        if not r:
            break


def upgrade():
    with session_scope(ignore_soft_deletes=False, versioned=False)\
            as db_session:
        for message in page_query(db_session.query(Message)):
            # calculate_sanitized_body has the side effect of computing the
            # right snippet
            message.calculate_sanitized_body()
    db_session.commit()


def downgrade():
    pass
