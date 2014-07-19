"""per-provider table split

Revision ID: 1c3f1812f2d9
Revises: 482338e7a7d6
Create Date: 2014-03-19 17:55:44.578515

"""

# revision identifiers, used by Alembic.
revision = '1c3f1812f2d9'
down_revision = '482338e7a7d6'

from alembic import op
import sqlalchemy as sa

from sqlalchemy.sql import table, column
from sqlalchemy.ext.declarative import declarative_base

from inbox.models.session import session_scope
from inbox.ignition import main_engine
engine = main_engine()

Base = declarative_base()
Base.metadata.reflect(engine)


def upgrade():
    genericize_imapaccount()
    genericize_thread()
    genericize_namespace_contact_foldersync()


def downgrade():
    downgrade_imapaccount()
    downgrade_imapthread()
    downgrade_namespace_contact_foldersync()


# Upgrade funtions:
def genericize_imapaccount():
    class ImapAccount_(Base):
        __table__ = Base.metadata.tables['imapaccount']

    # Get data from columns-to-be-dropped
    with session_scope() as db_session:
        results = db_session.query(ImapAccount_.id,
                                   ImapAccount_.imap_host).all()

    to_insert = [dict(id=r[0], imap_host=r[1]) for r in results]

    # Rename table, add new columns.
    op.rename_table('imapaccount', 'account')
    op.add_column('account', sa.Column('type', sa.String(16)))

    # Create new table, insert data
    # The table
    op.create_table('imapaccount',
                    sa.Column('imap_host', sa.String(512)),
                    sa.Column('id', sa.Integer()),
                    sa.ForeignKeyConstraint(['id'], ['account.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'))

    # The ad-hoc table for insert
    table_ = table('imapaccount',
                   column('imap_host', sa.String()),
                   column('id', sa.Integer))
    if to_insert:
        op.bulk_insert(table_, to_insert)

    # Drop columns now
    op.drop_column('account', 'imap_host')


def genericize_thread():
    class Thread_(Base):
        __table__ = Base.metadata.tables['thread']

    # Get data from columns-to-be-dropped
    with session_scope() as db_session:
        results = db_session.query(Thread_.id, Thread_.g_thrid).all()

    to_insert = [dict(id=r[0], g_thrid=r[1]) for r in results]

    # Add new columns
    op.add_column('thread', sa.Column('type', sa.String(16)))

    # Create new table, insert data
    # The table
    op.create_table('imapthread',
                    sa.Column('g_thrid', sa.BigInteger(), nullable=True,
                              index=True),
                    sa.Column('id', sa.Integer()),
                    sa.ForeignKeyConstraint(['id'], ['thread.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'))

    # The ad-hoc table for insert
    table_ = table('imapthread',
                   column('g_thrid', sa.BigInteger),
                   column('id', sa.Integer))
    if to_insert:
        op.bulk_insert(table_, to_insert)

    # Drop columns now
    op.drop_column('thread', 'g_thrid')


def genericize_namespace_contact_foldersync():
    # Namespace
    op.drop_constraint('namespace_ibfk_1', 'namespace', type_='foreignkey')
    op.alter_column('namespace', 'imapaccount_id',
                    new_column_name='account_id', existing_type=sa.Integer(),
                    existing_nullable=True)

    op.create_foreign_key('namespace_ibfk_1', 'namespace', 'account',
                          ['account_id'], ['id'], ondelete='CASCADE')

    # Contact
    op.drop_constraint('contact_ibfk_1', 'contact', type_='foreignkey')
    op.alter_column('contact', 'imapaccount_id',
                    new_column_name='account_id', existing_type=sa.Integer(),
                    existing_nullable=False)

    op.create_foreign_key('contact_ibfk_1', 'contact', 'account',
                          ['account_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('foldersync_ibfk_1', 'foldersync', type_='foreignkey')
    op.alter_column('foldersync', 'imapaccount_id',
                    new_column_name='account_id', existing_type=sa.Integer(),
                    existing_nullable=False)

    op.create_foreign_key('foldersync_ibfk_1', 'foldersync', 'account',
                          ['account_id'], ['id'], ondelete='CASCADE')


# Downgrade functions:
def downgrade_imapaccount():
    class ImapAccount_(Base):
        __table__ = Base.metadata.tables['imapaccount']

    # Get data from table-to-be-dropped
    with session_scope() as db_session:
        results = db_session.query(ImapAccount_.id,
                                   ImapAccount_.imap_host).all()
    to_insert = [dict(id=r[0], imap_host=r[1]) for r in results]

    # Drop columns, add new columns + insert data
    op.drop_column('account', 'type')
    op.add_column('account', sa.Column('imap_host', sa.String(512)))

    table_ = table('account',
                   column('imap_host', sa.String(512)),
                   column('id', sa.Integer))

    for r in to_insert:
        op.execute(
            table_.update().
            where(table_.c.id == r['id']).
            values({'imap_host': r['imap_host']})
        )

    # Table switch-over
    op.drop_constraint('imapuid_ibfk_1', 'imapuid', type_='foreignkey')
    op.drop_constraint('uidvalidity_ibfk_1', 'uidvalidity', type_='foreignkey')
    op.drop_constraint('foldersync_ibfk_1', 'foldersync', type_='foreignkey')
    op.drop_table('imapaccount')

    op.rename_table('account', 'imapaccount')

    op.create_foreign_key('imapuid_ibfk_1', 'imapuid', 'imapaccount',
                          ['imapaccount_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('uidvalidity_ibfk_1', 'uidvalidity', 'imapaccount',
                          ['imapaccount_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('foldersync_ibfk_1', 'foldersync', 'imapaccount',
                          ['account_id'], ['id'], ondelete='CASCADE')


def downgrade_imapthread():
    class ImapThread_(Base):
        __table__ = Base.metadata.tables['imapthread']

    # Get data from table-to-be-dropped
    with session_scope() as db_session:
        results = db_session.query(ImapThread_.id, ImapThread_.g_thrid).all()
    to_insert = [dict(id=r[0], g_thrid=r[1]) for r in results]

    # Drop columns, add new columns + insert data
    op.drop_column('thread', 'type')
    op.add_column('thread', sa.Column('g_thrid', sa.BigInteger(),
                                      nullable=True, index=True))
    table_ = table('thread',
                   column('g_thrid', sa.BigInteger),
                   column('id', sa.Integer))

    for r in to_insert:
        op.execute(
            table_.update().
            where(table_.c.id == r['id']).
            values({'g_thrid': r['g_thrid']})
        )

    # Drop table
    op.drop_table('imapthread')


def downgrade_namespace_contact_foldersync():
    # Namespace
    op.drop_constraint('namespace_ibfk_1', 'namespace', type_='foreignkey')
    op.alter_column('namespace', 'account_id',
                    new_column_name='imapaccount_id',
                    existing_type=sa.Integer(),
                    existing_nullable=True)
    op.create_foreign_key('namespace_ibfk_1', 'namespace', 'imapaccount',
                          ['imapaccount_id'], ['id'], ondelete='CASCADE')

    # Contact
    op.drop_constraint('contact_ibfk_1', 'contact', type_='foreignkey')
    op.alter_column('contact', 'account_id',
                    new_column_name='imapaccount_id',
                    existing_type=sa.Integer(),
                    existing_nullable=False)

    op.create_foreign_key('contact_ibfk_1', 'contact', 'imapaccount',
                          ['imapaccount_id'], ['id'], ondelete='CASCADE')

    # Foldersync
    op.drop_constraint('foldersync_ibfk_1', 'foldersync', type_='foreignkey')
    op.alter_column('foldersync', 'account_id',
                    new_column_name='imapaccount_id',
                    existing_type=sa.Integer(),
                    existing_nullable=False)

    op.create_foreign_key('foldersync_ibfk_1', 'foldersync', 'imapaccount',
                          ['imapaccount_id'], ['id'], ondelete='CASCADE')
