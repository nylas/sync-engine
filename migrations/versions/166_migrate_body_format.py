"""migrate body format

Revision ID: 3d4f5741e1d7
Revises: 29698176aa8d
Create Date: 2015-05-10 03:16:04.846781

"""

# revision identifiers, used by Alembic.
revision = '3d4f5741e1d7'
down_revision = '29698176aa8d'

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import load_only


CHUNK_SIZE = 1000


def upgrade():
    from inbox.ignition import main_engine
    from inbox.models.session import session_scope
    from inbox.security.blobstorage import encode_blob
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Message(Base):
        __table__ = Base.metadata.tables['message']

    with session_scope(versioned=False) as db_session:
        max_id, = db_session.query(sa.func.max(Message.id)).one()
        for i in range(0, max_id, CHUNK_SIZE):
            messages = db_session.query(Message). \
                filter(Message.id > i, Message.id <= i + CHUNK_SIZE). \
                options(load_only('_compacted_body', '_sanitized_body'))
            for message in messages:
                if message._compacted_body is None:
                    message._compacted_body = encode_blob(
                        message._sanitized_body.encode('utf-8'))
            db_session.commit()


def downgrade():
    pass
