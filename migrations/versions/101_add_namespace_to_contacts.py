"""add_namespace_to_contacts

Revision ID: 3bb01fcc755e
Revises:5a68ac0e3e9
Create Date: 2014-09-22 02:33:53.301883

"""

# revision identifiers, used by Alembic.
revision = '3bb01fcc755e'
down_revision = '5a68ac0e3e9'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text('''
        ALTER TABLE contact
            ADD COLUMN namespace_id INTEGER,
            ADD FOREIGN KEY(namespace_id) REFERENCES namespace (id)
            '''))

    conn.execute(text('''
        UPDATE contact JOIN namespace ON contact.account_id=namespace.account_id
        SET contact.namespace_id=namespace.id'''))

    conn.execute(text('''
        ALTER TABLE contact
            DROP INDEX uid,
            DROP FOREIGN KEY contact_ibfk_1,
            ADD CONSTRAINT uid UNIQUE (uid, source, namespace_id, provider_name),
            DROP COLUMN account_id
            '''))


def downgrade():
    raise Exception()
