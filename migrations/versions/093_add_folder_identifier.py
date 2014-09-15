"""Add Folder.identifier

Revision ID: 159607944f52
Revises: 4b07b67498e1
Create Date: 2014-09-14 08:43:59.410902

"""

# revision identifiers, used by Alembic.
revision = '159607944f52'
down_revision = '63dc7f205da'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    from inbox.models.constants import MAX_INDEXABLE_LENGTH

    conn = op.get_bind()

    conn.execute(text("""
        ALTER TABLE folder
            DROP INDEX account_id,
            ADD COLUMN identifier VARCHAR(:len) NULL,
            ADD CONSTRAINT account_id UNIQUE (account_id, name, canonical_name, identifier)"""), len=MAX_INDEXABLE_LENGTH)

    # For eas accounts -
    # set identifier=canonical_name
    # then canonical_name=NULL (so non-Inbox canonical tags will be set correctly henceforth)
    conn.execute(text("""
        UPDATE folder INNER JOIN account ON folder.account_id=account.id
        SET folder.identifier=folder.canonical_name, folder.canonical_name=NULL
        WHERE account.type='easaccount'
        """))

    # Set Inbox-canonical tags: inbox, sent, drafts, trash, archive too
    q = """
    UPDATE folder INNER JOIN account ON folder.id=account.inbox_folder_id SET folder.canonical_name='inbox' WHERE account.type='easaccount'
    """
    conn.execute(text(q))

    q = """
    UPDATE folder INNER JOIN account ON folder.id=account.sent_folder_id SET folder.canonical_name='sent' WHERE account.type='easaccount'
    """
    conn.execute(text(q))

    q = """
    UPDATE folder INNER JOIN account ON folder.id=account.drafts_folder_id SET folder.canonical_name='drafts' WHERE account.type='easaccount'
    """
    conn.execute(text(q))

    q = """
    UPDATE folder INNER JOIN account ON folder.id=account.trash_folder_id SET folder.canonical_name='trash' WHERE account.type='easaccount'
    """
    conn.execute(text(q))

    q = """
    UPDATE folder INNER JOIN account ON folder.id=account.archive_folder_id SET folder.canonical_name='archive' WHERE account.type='easaccount'
    """
    conn.execute(text(q))

    # We're not going to back-fix tags on threads.


def downgrade():
    raise Exception("Can't.")
