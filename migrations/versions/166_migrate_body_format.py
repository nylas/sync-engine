"""migrate body format

Revision ID: 3d4f5741e1d7
Revises: 29698176aa8d
Create Date: 2015-05-10 03:16:04.846781

"""

# revision identifiers, used by Alembic.
revision = '3d4f5741e1d7'
down_revision = '29698176aa8d'

import sqlalchemy as sa


CHUNK_SIZE = 1000


def upgrade():
    from inbox.models import Message
    from inbox.models.session import session_scope
    with session_scope() as db_session:
        max_id, = db_session.query(sa.func.max(Message.id)).one()
        for i in range(0, max_id, CHUNK_SIZE):
            messages = db_session.query(Message). \
                filter(Message.id > i, Message.id <= i + CHUNK_SIZE). \
                options(sa.orm.load_only('_compacted_body', '_sanitized_body'))
            for message in messages:
                if message._compacted_body is None:
                    message.body = message._sanitized_body
            db_session.commit()


def downgrade():
    pass
