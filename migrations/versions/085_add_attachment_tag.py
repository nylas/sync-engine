"""add attachment tag

Revision ID: 294200d809c8
Revises:10db12da2005
Create Date: 2014-08-22 20:15:59.937498

"""

# revision identifiers, used by Alembic.
revision = '294200d809c8'
down_revision = '10db12da2005'


def upgrade():
    from inbox.models.session import session_scope
    from inbox.models import Namespace, Tag, Thread
    from inbox.sqlalchemy_ext.util import safer_yield_per
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload
    with session_scope() as db_session:
        # Create the attachment tag
        for ns in db_session.query(Namespace):
            Tag.create_canonical_tags(ns, db_session)

        thread_count, = db_session.query(func.count(Thread.id)).one()
        q = db_session.query(Thread).options(joinedload(Thread.messages))
        processed_count = 0
        for thr in safer_yield_per(q, Thread.id, 1, thread_count):
            if any(m.attachments for m in thr.messages):
                attachment_tag = thr.namespace.tags['attachment']
                thr.apply_tag(attachment_tag)
            processed_count += 1
            print processed_count


def downgrade():
    # No actual schema changes, don't need to do anything to roll back.
    pass
