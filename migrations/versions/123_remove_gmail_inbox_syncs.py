"""Remove gmail inbox syncs

Revision ID: 3c743bd31ee2
Revises:476c5185121b
Create Date: 2014-12-08 03:53:36.829238

"""

# revision identifiers, used by Alembic.
revision = '3c743bd31ee2'
down_revision = '476c5185121b'


def upgrade():
    # Remove UIDs and sync status for inbox IMAP syncs -- otherwise
    # archives/deletes may not be synced correctly.
    from inbox.models.backends.imap import ImapFolderSyncStatus, ImapUid
    from inbox.models.backends.gmail import GmailAccount
    from inbox.models.session import session_scope
    from inbox.status.sync import get_redis_client
    redis_client = get_redis_client()
    with session_scope(ignore_soft_deletes=False, versioned=False) as \
            db_session:
        for account in db_session.query(GmailAccount):
            if account.inbox_folder is None:
                # May be the case for accounts that we can't sync, e.g. due to
                # All Mail being disabled in IMAP.
                continue
            q = db_session.query(ImapFolderSyncStatus).filter(
                ImapFolderSyncStatus.account_id == account.id,
                ImapFolderSyncStatus.folder_id == account.inbox_folder.id)
            q.delete()

            q = db_session.query(ImapUid).filter(
                ImapUid.account_id == account.id,
                ImapUid.folder_id == account.inbox_folder.id)
            q.delete()
            db_session.commit()

            # Also remove the corresponding status entry from Redis.
            key = '{}:{}'.format(account.id, account.inbox_folder.id)
            redis_client.hdel(key, '0')



def downgrade():
    pass
