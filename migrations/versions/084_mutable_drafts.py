"""Mutable drafts

Revision ID: 10db12da2005
Revises: 43e5867a6ef1
Create Date: 2014-08-22 22:04:10.763048

"""

# revision identifiers, used by Alembic.
revision = '10db12da2005'
down_revision = '10a1129fe685'

from alembic import op
from sqlalchemy.sql import text

import sqlalchemy as sa


def upgrade():
    from inbox.sqlalchemy_ext.util import JSON
    op.add_column('actionlog',
                  sa.Column('extra_args', JSON(), nullable=True))

    conn = op.get_bind()

    conn.execute(text("""
        ALTER TABLE message ADD COLUMN version BINARY(16),
                            DROP FOREIGN KEY message_ibfk_3
                      """))

    parent_drafts_ids = [id_ for id_, in conn.execute(text(
        """
        SELECT message.parent_draft_id from message
        WHERE message.is_created = 1
            AND message.is_draft = 1
            AND message.parent_draft_id IS NOT NULL
        """))]
    print parent_drafts_ids
    if parent_drafts_ids:
        # delete old parent drafts
        conn.execute(text("""
            DELETE FROM message
            WHERE message.is_created = 1 AND message.is_draft = 1
            AND message.id IN :parent_drafts_ids"""),
                     parent_drafts_ids=parent_drafts_ids)

    conn.execute(text("""
        UPDATE message SET message.version = message.public_id
        WHERE message.is_created = 1 AND message.is_draft = 1
        """))

    op.drop_column('message', 'parent_draft_id')


def downgrade():
    raise Exception('No.')
