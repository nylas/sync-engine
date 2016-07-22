"""calculate receivedrecentdate for threads

Revision ID: 691fa97024d
Revises: 2758cefad87d
Create Date: 2015-07-20 23:47:41.297327

"""

# revision identifiers, used by Alembic.
revision = '691fa97024d'
down_revision = '2758cefad87d'


# solution from http://stackoverflow.com/a/1217947
def page_query(q):
    CHUNK_SIZE = 500
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
    from inbox.models import Message, Thread
    from inbox.models.session import session_scope
    from sqlalchemy import desc
    from sqlalchemy.sql import not_

    with session_scope(versioned=False) as db_session:
        for thread in page_query(db_session.query(Thread)):
            last_message = db_session.query(Message). \
                filter(Message.thread_id == thread.id,
                       not_(Message.categories.any(name="sent"))). \
                order_by(desc(Message.received_date)).first()
            if last_message:
                thread.receivedrecentdate = last_message.received_date

    db_session.commit()


def downgrade():
    pass
