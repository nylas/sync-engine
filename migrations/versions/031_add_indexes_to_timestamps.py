"""Adds indexes to columns created_at, deleted_at, updated_at

Revision ID: 55f0ff54c776
Revises: 1b6ceae51b43
Create Date: 2014-05-20 05:45:52.568827

"""

# revision identifiers, used by Alembic.
revision = '55f0ff54c776'
down_revision = '1b6ceae51b43'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from sqlalchemy.ext.declarative import declarative_base


def upgrade():
    from inbox.ignition import engine
    Base = declarative_base()
    Base.metadata.reflect(engine)

    op.create_index('ix_account_created_at', 'account', ['created_at'], unique=False)
    op.create_index('ix_account_deleted_at', 'account', ['deleted_at'], unique=False)
    op.create_index('ix_account_updated_at', 'account', ['updated_at'], unique=False)
    op.create_index('ix_block_created_at', 'block', ['created_at'], unique=False)
    op.create_index('ix_block_deleted_at', 'block', ['deleted_at'], unique=False)
    op.create_index('ix_block_updated_at', 'block', ['updated_at'], unique=False)
    op.create_index('ix_contact_created_at', 'contact', ['created_at'], unique=False)
    op.create_index('ix_contact_deleted_at', 'contact', ['deleted_at'], unique=False)
    op.create_index('ix_contact_updated_at', 'contact', ['updated_at'], unique=False)

    if 'easfoldersync' in Base.metadata.tables:
        op.create_index('ix_easfoldersync_created_at', 'easfoldersync', ['created_at'], unique=False)
        op.create_index('ix_easfoldersync_deleted_at', 'easfoldersync', ['deleted_at'], unique=False)
        op.create_index('ix_easfoldersync_updated_at', 'easfoldersync', ['updated_at'], unique=False)

    if 'easuid' in Base.metadata.tables:
        op.create_index('easuid_easaccount_id_folder_id', 'easuid', ['easaccount_id', 'folder_id'], unique=False)
        op.create_index('ix_easuid_created_at', 'easuid', ['created_at'], unique=False)
        op.create_index('ix_easuid_deleted_at', 'easuid', ['deleted_at'], unique=False)
        op.create_index('ix_easuid_updated_at', 'easuid', ['updated_at'], unique=False)

    op.create_index('ix_folder_created_at', 'folder', ['created_at'], unique=False)
    op.create_index('ix_folder_deleted_at', 'folder', ['deleted_at'], unique=False)
    op.create_index('ix_folder_updated_at', 'folder', ['updated_at'], unique=False)
    op.create_index('ix_folderitem_created_at', 'folderitem', ['created_at'], unique=False)
    op.create_index('ix_folderitem_deleted_at', 'folderitem', ['deleted_at'], unique=False)
    op.create_index('ix_folderitem_updated_at', 'folderitem', ['updated_at'], unique=False)

    op.create_index('ix_foldersync_created_at', 'foldersync', ['created_at'], unique=False)
    op.create_index('ix_foldersync_deleted_at', 'foldersync', ['deleted_at'], unique=False)
    op.create_index('ix_foldersync_updated_at', 'foldersync', ['updated_at'], unique=False)

    op.create_index('ix_imapuid_created_at', 'imapuid', ['created_at'], unique=False)
    op.create_index('ix_imapuid_deleted_at', 'imapuid', ['deleted_at'], unique=False)
    op.create_index('ix_imapuid_updated_at', 'imapuid', ['updated_at'], unique=False)
    op.create_index('ix_lens_created_at', 'lens', ['created_at'], unique=False)
    op.create_index('ix_lens_deleted_at', 'lens', ['deleted_at'], unique=False)
    op.create_index('ix_lens_updated_at', 'lens', ['updated_at'], unique=False)
    op.create_index('ix_message_created_at', 'message', ['created_at'], unique=False)
    op.create_index('ix_message_deleted_at', 'message', ['deleted_at'], unique=False)
    op.create_index('ix_message_updated_at', 'message', ['updated_at'], unique=False)
    op.create_index('ix_messagecontactassociation_created_at', 'messagecontactassociation', ['created_at'], unique=False)
    op.create_index('ix_messagecontactassociation_deleted_at', 'messagecontactassociation', ['deleted_at'], unique=False)
    op.create_index('ix_messagecontactassociation_updated_at', 'messagecontactassociation', ['updated_at'], unique=False)
    op.create_index('ix_namespace_created_at', 'namespace', ['created_at'], unique=False)
    op.create_index('ix_namespace_deleted_at', 'namespace', ['deleted_at'], unique=False)
    op.create_index('ix_namespace_updated_at', 'namespace', ['updated_at'], unique=False)
    op.create_index('ix_searchsignal_created_at', 'searchsignal', ['created_at'], unique=False)
    op.create_index('ix_searchsignal_deleted_at', 'searchsignal', ['deleted_at'], unique=False)
    op.create_index('ix_searchsignal_updated_at', 'searchsignal', ['updated_at'], unique=False)
    op.create_index('ix_searchtoken_created_at', 'searchtoken', ['created_at'], unique=False)
    op.create_index('ix_searchtoken_deleted_at', 'searchtoken', ['deleted_at'], unique=False)
    op.create_index('ix_searchtoken_updated_at', 'searchtoken', ['updated_at'], unique=False)
    op.create_index('ix_thread_created_at', 'thread', ['created_at'], unique=False)
    op.create_index('ix_thread_deleted_at', 'thread', ['deleted_at'], unique=False)
    op.create_index('ix_thread_updated_at', 'thread', ['updated_at'], unique=False)
    op.create_index('ix_transaction_created_at', 'transaction', ['created_at'], unique=False)
    op.create_index('ix_transaction_deleted_at', 'transaction', ['deleted_at'], unique=False)
    op.create_index('ix_transaction_updated_at', 'transaction', ['updated_at'], unique=False)
    op.create_index('ix_uidvalidity_created_at', 'uidvalidity', ['created_at'], unique=False)
    op.create_index('ix_uidvalidity_deleted_at', 'uidvalidity', ['deleted_at'], unique=False)
    op.create_index('ix_uidvalidity_updated_at', 'uidvalidity', ['updated_at'], unique=False)

    op.create_index('ix_usertag_created_at', 'usertag', ['created_at'], unique=False)
    op.create_index('ix_usertag_deleted_at', 'usertag', ['deleted_at'], unique=False)
    op.create_index('ix_usertag_public_id', 'usertag', ['public_id'], unique=False)
    op.create_index('ix_usertag_updated_at', 'usertag', ['updated_at'], unique=False)

    op.create_index('ix_usertagitem_created_at', 'usertagitem', ['created_at'], unique=False)
    op.create_index('ix_usertagitem_deleted_at', 'usertagitem', ['deleted_at'], unique=False)
    op.create_index('ix_usertagitem_updated_at', 'usertagitem', ['updated_at'], unique=False)
    op.create_index('ix_webhook_created_at', 'webhook', ['created_at'], unique=False)
    op.create_index('ix_webhook_deleted_at', 'webhook', ['deleted_at'], unique=False)
    op.create_index('ix_webhook_updated_at', 'webhook', ['updated_at'], unique=False)


def downgrade():
    op.drop_index('ix_webhook_updated_at', table_name='webhook')
    op.drop_index('ix_webhook_deleted_at', table_name='webhook')
    op.drop_index('ix_webhook_created_at', table_name='webhook')
    op.drop_index('ix_usertagitem_updated_at', table_name='usertagitem')
    op.drop_index('ix_usertagitem_deleted_at', table_name='usertagitem')
    op.drop_index('ix_usertagitem_created_at', table_name='usertagitem')

    op.drop_index('ix_usertag_updated_at', table_name='usertag')
    op.drop_index('ix_usertag_public_id', table_name='usertag')
    op.drop_index('ix_usertag_deleted_at', table_name='usertag')
    op.drop_index('ix_usertag_created_at', table_name='usertag')

    op.drop_index('ix_uidvalidity_updated_at', table_name='uidvalidity')
    op.drop_index('ix_uidvalidity_deleted_at', table_name='uidvalidity')
    op.drop_index('ix_uidvalidity_created_at', table_name='uidvalidity')
    op.drop_index('ix_transaction_updated_at', table_name='transaction')
    op.drop_index('ix_transaction_deleted_at', table_name='transaction')
    op.drop_index('ix_transaction_created_at', table_name='transaction')
    op.drop_index('ix_thread_updated_at', table_name='thread')
    op.drop_index('ix_thread_deleted_at', table_name='thread')
    op.drop_index('ix_thread_created_at', table_name='thread')
    op.drop_index('ix_searchtoken_updated_at', table_name='searchtoken')
    op.drop_index('ix_searchtoken_deleted_at', table_name='searchtoken')
    op.drop_index('ix_searchtoken_created_at', table_name='searchtoken')
    op.drop_index('ix_searchsignal_updated_at', table_name='searchsignal')
    op.drop_index('ix_searchsignal_deleted_at', table_name='searchsignal')
    op.drop_index('ix_searchsignal_created_at', table_name='searchsignal')
    op.drop_index('ix_namespace_updated_at', table_name='namespace')
    op.drop_index('ix_namespace_deleted_at', table_name='namespace')
    op.drop_index('ix_namespace_created_at', table_name='namespace')
    op.drop_index('ix_messagecontactassociation_updated_at', table_name='messagecontactassociation')
    op.drop_index('ix_messagecontactassociation_deleted_at', table_name='messagecontactassociation')
    op.drop_index('ix_messagecontactassociation_created_at', table_name='messagecontactassociation')
    op.drop_index('ix_message_updated_at', table_name='message')
    op.drop_index('ix_message_deleted_at', table_name='message')
    op.drop_index('ix_message_created_at', table_name='message')
    op.drop_index('ix_lens_updated_at', table_name='lens')
    op.drop_index('ix_lens_deleted_at', table_name='lens')
    op.drop_index('ix_lens_created_at', table_name='lens')
    op.drop_index('ix_imapuid_updated_at', table_name='imapuid')
    op.drop_index('ix_imapuid_deleted_at', table_name='imapuid')
    op.drop_index('ix_imapuid_created_at', table_name='imapuid')

    op.drop_index('ix_foldersync_updated_at', table_name='foldersync')
    op.drop_index('ix_foldersync_deleted_at', table_name='foldersync')
    op.drop_index('ix_foldersync_created_at', table_name='foldersync')

    op.drop_index('ix_folderitem_updated_at', table_name='folderitem')
    op.drop_index('ix_folderitem_deleted_at', table_name='folderitem')
    op.drop_index('ix_folderitem_created_at', table_name='folderitem')
    op.drop_index('ix_folder_updated_at', table_name='folder')
    op.drop_index('ix_folder_deleted_at', table_name='folder')
    op.drop_index('ix_folder_created_at', table_name='folder')

    from inbox.ignition import engine
    Base = declarative_base()
    Base.metadata.reflect(engine)

    if 'easuid' in Base.metadata.tables:
        op.drop_index('ix_easuid_updated_at', table_name='easuid')
        op.drop_index('ix_easuid_deleted_at', table_name='easuid')
        op.drop_index('ix_easuid_created_at', table_name='easuid')
        op.drop_index('easuid_easaccount_id_folder_id', table_name='easuid')

    if 'easfoldersync' in Base.metadata.tables:
        op.drop_index('ix_easfoldersync_updated_at', table_name='easfoldersync')
        op.drop_index('ix_easfoldersync_deleted_at', table_name='easfoldersync')
        op.drop_index('ix_easfoldersync_created_at', table_name='easfoldersync')
    op.drop_index('ix_contact_updated_at', table_name='contact')
    op.drop_index('ix_contact_deleted_at', table_name='contact')
    op.drop_index('ix_contact_created_at', table_name='contact')
    op.drop_index('ix_block_updated_at', table_name='block')
    op.drop_index('ix_block_deleted_at', table_name='block')
    op.drop_index('ix_block_created_at', table_name='block')

    op.drop_index('ix_account_updated_at', table_name='account')
    op.drop_index('ix_account_deleted_at', table_name='account')
    op.drop_index('ix_account_created_at', table_name='account')
