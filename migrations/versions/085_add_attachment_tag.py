"""add attachment tag

Revision ID: 294200d809c8
Revises:10db12da2005
Create Date: 2014-08-22 20:15:59.937498

"""

# revision identifiers, used by Alembic.
revision = '294200d809c8'
down_revision = '10db12da2005'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    from inbox.models.session import session_scope
    from inbox.models import Namespace, Tag
    with session_scope() as db_session:
        # Create the attachment tag
        print "creating canonical tags..."
        for ns in db_session.query(Namespace):
            Tag.create_canonical_tags(ns, db_session)
            db_session.commit()

    conn = op.get_bind()

    tag_id_for_namespace = dict(
        [(namespace_id, tag_id) for namespace_id, tag_id in conn.execute(
            text("SELECT namespace_id, id FROM tag WHERE name = 'attachment'"))])
    print "have attachment tag for", len(tag_id_for_namespace), "namespaces"

    existing_tagitems = set([thread_id for thread_id, in conn.execute(text(
        "SELECT distinct(thread_id) FROM tagitem WHERE tag_id IN :tag_ids"),
        tag_ids=set(tag_id_for_namespace.values()))])

    q = """SELECT distinct(thread.id), namespace_id FROM thread
               INNER JOIN message ON thread.id = message.thread_id
               INNER JOIN part ON part.message_id = message.id
           WHERE part.content_disposition IS NOT NULL
        """
    if existing_tagitems:
        print "skipping", len(existing_tagitems), \
            "threads which already have the tag attachment"

        q += " AND thread.id NOT IN :existing_tagitems"
    q += " ORDER BY thread.id ASC"

    for thread_id, namespace_id in \
            conn.execute(text(q), existing_tagitems=existing_tagitems):
        print thread_id
        # We could bulk insert, but don't bother.
        conn.execute(text(
            """
            INSERT INTO tagitem (created_at, updated_at, thread_id, tag_id)
            VALUES (UTC_TIMESTAMP(), UTC_TIMESTAMP(), :thread_id, :tag_id)
            """),
            thread_id=thread_id, tag_id=tag_id_for_namespace[namespace_id])


def downgrade():
    # No actual schema changes, don't need to do anything to roll back.
    pass
