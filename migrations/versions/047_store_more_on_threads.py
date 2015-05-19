"""Store more on threads

Revision ID: 161b88c17615
Revises: 38d78543f8be
Create Date: 2014-06-27 01:46:28.773074

"""

# revision identifiers, used by Alembic.
revision = '161b88c17615'
down_revision = '38d78543f8be'

import itertools
from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.sqlalchemy_ext.util import JSON
    op.add_column('thread', sa.Column('participants', JSON,
                                      nullable=True))
    op.add_column('thread', sa.Column('message_public_ids', JSON,
                                      nullable=True))
    op.add_column('thread', sa.Column('snippet', sa.String(191),
                                      nullable=True))

    from inbox.models.session import session_scope
    from inbox.models import Thread

    with session_scope(versioned=False) as db_session:
        num_threads, = db_session.query(sa.func.max(Thread.id)).one()
        if num_threads is None:
            # There aren't actually any threads to update.
            return
        for pointer in range(0, num_threads + 1, 1000):
            print pointer
            for thread in db_session.query(Thread).filter(
                    Thread.id >= pointer,
                    Thread.id < pointer + 1000):
                message = thread.messages[-1]
                thread.snippet = thread.messages[-1].snippet
                participant_set = set()
                for message in thread.messages:
                    participant_set.update({tuple(p) for p in itertools.chain(
                        message.from_addr, message.to_addr, message.cc_addr,
                        message.bcc_addr)})
                thread.participants = list(participant_set)
                thread.message_public_ids = [m.public_id for m in
                                             thread.messages]
                db_session.add(thread)
            db_session.commit()


def downgrade():
    op.drop_column('thread', 'participants')
    op.drop_column('thread', 'message_public_ids')
    op.drop_column('thread', 'snippet')
