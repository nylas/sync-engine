"""cascade folder deletes to imapuid

Otherwise, since this fk is NOT NULL, deleting a folder which has associated
imapuids still existing will cause a database IntegrityError. Only the mail
sync engine does such a thing. Nothing else should be deleting folders,
hard or soft.

This also fixes a problem where if e.g. someone disables their Spam folder
from showing up in Gmail IMAP, the server will crash trying to delete that
folder the account.spam_folder_id constraint fails.

Revision ID: 350a08df27ee
Revises: 1eab2619cc4f
Create Date: 2014-05-25 01:40:21.762119

"""

# revision identifiers, used by Alembic.
revision = '350a08df27ee'
down_revision = '1eab2619cc4f'

from alembic import op


def upgrade():
    op.drop_constraint('imapuid_ibfk_3', 'imapuid', type_='foreignkey')
    op.create_foreign_key('imapuid_ibfk_3', 'imapuid', 'folder',
                          ['folder_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('account_ibfk_2', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_2', 'account', 'folder',
                          ['inbox_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('account_ibfk_3', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_3', 'account', 'folder',
                          ['sent_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('account_ibfk_4', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_4', 'account', 'folder',
                          ['drafts_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('account_ibfk_5', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_5', 'account', 'folder',
                          ['spam_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('account_ibfk_6', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_6', 'account', 'folder',
                          ['trash_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('account_ibfk_7', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_7', 'account', 'folder',
                          ['archive_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('account_ibfk_8', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_8', 'account', 'folder',
                          ['all_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('account_ibfk_9', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_9', 'account', 'folder',
                          ['starred_folder_id'], ['id'], ondelete='SET NULL')
    # for some reason this was left out of migration 024, so might not exist
    try:
        op.drop_constraint('account_ibfk_10', 'account', type_='foreignkey')
    except:
        pass
    op.create_foreign_key('account_ibfk_10', 'account', 'folder',
                          ['important_folder_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint('imapuid_ibfk_3', 'imapuid', type_='foreignkey')
    op.create_foreign_key('imapuid_ibfk_3', 'imapuid', 'folder',
                          ['folder_id'], ['id'])
    op.drop_constraint('account_ibfk_2', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_2', 'account', 'folder',
                          ['inbox_folder_id'], ['id'])
    op.drop_constraint('account_ibfk_3', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_3', 'account', 'folder',
                          ['sent_folder_id'], ['id'])
    op.drop_constraint('account_ibfk_4', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_4', 'account', 'folder',
                          ['drafts_folder_id'], ['id'])
    op.drop_constraint('account_ibfk_5', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_5', 'account', 'folder',
                          ['spam_folder_id'], ['id'])
    op.drop_constraint('account_ibfk_6', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_6', 'account', 'folder',
                          ['trash_folder_id'], ['id'])
    op.drop_constraint('account_ibfk_7', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_7', 'account', 'folder',
                          ['archive_folder_id'], ['id'])
    op.drop_constraint('account_ibfk_8', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_8', 'account', 'folder',
                          ['all_folder_id'], ['id'])
    op.drop_constraint('account_ibfk_9', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_9', 'account', 'folder',
                          ['starred_folder_id'], ['id'])
    op.drop_constraint('account_ibfk_10', 'account', type_='foreignkey')
    op.create_foreign_key('account_ibfk_10', 'account', 'folder',
                          ['important_folder_id'], ['id'])
