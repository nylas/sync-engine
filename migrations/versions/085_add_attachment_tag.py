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
        print "creating canonical tags..."
        for ns in db_session.query(Namespace):
            Tag.create_canonical_tags(ns, db_session)
            db_session.commit()

        thread_count = db_session.query(func.count(Thread.id)).scalar()
        print "\nchecking for attachment tag on {} threads".format(thread_count)
        q = db_session.query(Thread).options(joinedload(Thread.messages))
        processed_count = 0
        for thr in safer_yield_per(q, Thread.id, 1, 25):
            if any(m.attachments for m in thr.messages):
                attachment_tag = thr.namespace.tags['attachment']
                thr.apply_tag(attachment_tag)
            processed_count += 1
            if processed_count % 500 == 0:
                print processed_count
                db_session.commit()
        db_session.commit()


def downgrade():
    # No actual schema changes, don't need to do anything to roll back.
    pass
