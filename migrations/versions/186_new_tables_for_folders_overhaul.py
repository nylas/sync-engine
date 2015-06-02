"""new tables for folders overhaul

Revision ID: 23e204cd1d91
Revises:14692efd261b
Create Date: 2015-06-19 00:28:56.991030

"""

# revision identifiers, used by Alembic.
revision = '23e204cd1d91'
down_revision = '14692efd261b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'category',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.BINARY(16), nullable=False),
        sa.Column('namespace_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=191, collation='utf8mb4_bin'),
                  nullable=True),
        sa.Column('display_name', sa.String(length=191), nullable=False),
        sa.Column('type_', sa.Enum('folder', 'label'), nullable=False),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespace.id'],
                                name='category_fk1', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('namespace_id', 'name', 'display_name'),
        sa.UniqueConstraint('namespace_id', 'public_id')
    )
    op.create_index('ix_category_public_id', 'category', ['public_id'],
                    unique=False)
    op.create_index('ix_category_created_at', 'category', ['created_at'],
                    unique=False)
    op.create_index('ix_category_deleted_at', 'category', ['deleted_at'],
                    unique=False)
    op.create_index('ix_category_updated_at', 'category', ['updated_at'],
                    unique=False)
    op.create_table(
        'label',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=191, collation='utf8mb4_bin'),
                  nullable=False),
        sa.Column('canonical_name', sa.String(length=191), nullable=True),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['account.id'],
                                name='label_fk1', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], [u'category.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'name')
    )
    op.create_index('ix_label_created_at', 'label', ['created_at'],
                    unique=False)
    op.create_index('ix_label_deleted_at', 'label', ['deleted_at'],
                    unique=False)
    op.create_index('ix_label_updated_at', 'label', ['updated_at'],
                    unique=False)
    op.create_table(
        'messagecategory',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], [u'category.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], [u'message.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messagecategory_created_at', 'messagecategory',
                    ['created_at'], unique=False)
    op.create_index('ix_messagecategory_deleted_at', 'messagecategory',
                    ['deleted_at'], unique=False)
    op.create_index('ix_messagecategory_updated_at', 'messagecategory',
                    ['updated_at'], unique=False)
    op.create_index('message_category_ids', 'messagecategory',
                    ['message_id', 'category_id'], unique=False)
    op.create_table(
        'labelitem',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('imapuid_id', sa.Integer(), nullable=False),
        sa.Column('label_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['imapuid_id'], [u'imapuid.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['label_id'], [u'label.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('imapuid_label_ids', 'labelitem',
                    ['imapuid_id', 'label_id'], unique=False)
    op.create_index('ix_labelitem_created_at', 'labelitem', ['created_at'],
                    unique=False)
    op.create_index('ix_labelitem_deleted_at', 'labelitem', ['deleted_at'],
                    unique=False)
    op.create_index('ix_labelitem_updated_at', 'labelitem', ['updated_at'],
                    unique=False)
    op.add_column('folder',
                  sa.Column('category_id', sa.Integer(), nullable=True))
    op.create_foreign_key('folder_ibfk_2', 'folder',
                          'category', ['category_id'], ['id'])

    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if engine.has_table('easfoldersyncstatus'):
        op.add_column('easfoldersyncstatus',
                      sa.Column('category_id', sa.Integer(), nullable=True))
        op.create_foreign_key('easfoldersyncstatus_ibfk_3',
                              'easfoldersyncstatus', 'category',
                              ['category_id'], ['id'])

    op.add_column('message',
                  sa.Column('is_starred', sa.Boolean(),
                            server_default=sa.sql.expression.false(),
                            nullable=False))


def downgrade():
    raise Exception('Aw hell no')
