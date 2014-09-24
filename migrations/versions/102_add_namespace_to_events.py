"""add_namespace_to_events

Revision ID: 4d10bc835f44
Revises: 3bb01fcc755e
Create Date: 2014-09-22 03:28:18.437679

"""

# revision identifiers, used by Alembic.
revision = '4d10bc835f44'
down_revision = '3bb01fcc755e'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text('''
        ALTER TABLE event
            ADD COLUMN namespace_id INTEGER,
            ADD FOREIGN KEY(namespace_id) REFERENCES namespace (id)
            '''))

    conn.execute(text('''
        UPDATE event JOIN namespace ON event.account_id=namespace.account_id
        SET event.namespace_id=namespace.id'''))

    conn.execute(text('''
        ALTER TABLE event
            DROP INDEX uuid,
            DROP FOREIGN KEY event_ibfk_1,
            ADD CONSTRAINT uuid UNIQUE (uid, source, namespace_id, provider_name),
            DROP COLUMN account_id
            '''))


def downgrade():
    raise Exception()
