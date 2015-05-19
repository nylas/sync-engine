"""replace usertag by generic tag

Revision ID: 21878b1b3d4b
Revises: 24e085e152c0
Create Date: 2014-05-21 03:36:26.834916

"""

# revision identifiers, used by Alembic.
revision = '21878b1b3d4b'
down_revision = '24e085e152c0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('namespace_id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=191), nullable=False),
        sa.Column('name', sa.String(length=191), nullable=False),
        sa.Column('user_created', sa.Boolean(), nullable=False,
                  server_default=sa.sql.expression.false()),
        sa.Column('user_mutable', sa.Boolean(), nullable=False,
                  server_default=sa.sql.expression.true()),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespace.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('namespace_id', 'name'),
        sa.UniqueConstraint('namespace_id', 'public_id')
    )
    op.create_index('ix_tag_created_at', 'tag', ['created_at'], unique=False)
    op.create_index('ix_tag_deleted_at', 'tag', ['deleted_at'], unique=False)
    op.create_index('ix_tag_updated_at', 'tag', ['updated_at'], unique=False)
    op.create_table(
        'tagitem',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('thread_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['tag_id'], ['tag.id']),
        sa.ForeignKeyConstraint(['thread_id'], ['thread.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tagitem_created_at', 'tagitem', ['created_at'],
                    unique=False)
    op.create_index('ix_tagitem_deleted_at', 'tagitem', ['deleted_at'],
                    unique=False)
    op.create_index('ix_tagitem_updated_at', 'tagitem', ['updated_at'],
                    unique=False)
    op.drop_table(u'usertagitem')
    op.drop_table(u'usertag')

    op.alter_column('folder', 'public_id', new_column_name='canonical_name',
                    existing_nullable=True,
                    existing_type=sa.String(length=191))

    op.drop_column('folder', u'exposed_name')

    from inbox.models.session import session_scope
    # Doing this ties this migration to the state of the code at the time
    # of this commit. However, the alternative is to have a crazy long,
    # involved and error-prone recreation of the models and their behavior
    # here. (I tried it, and decided this way was better.)
    from inbox.models import FolderItem, Tag, Namespace

    with session_scope(versioned=False) as db_session:
        # create canonical tags that don't already exist.
        CANONICAL_TAG_NAMES = ['inbox', 'all', 'archive', 'drafts', 'send',
                               'sending', 'sent', 'spam', 'starred',
                               'unstarred', 'unread', 'replied', 'trash',
                               'file', 'attachment']
        for namespace in db_session.query(Namespace):
            existing_canonical_tags = db_session.query(Tag).filter(
                Tag.namespace == namespace,
                Tag.public_id.in_(CANONICAL_TAG_NAMES)).all()
            missing_canonical_names = set(CANONICAL_TAG_NAMES).difference(
                {tag.canonical_name for tag in existing_canonical_tags})
            for canonical_name in missing_canonical_names:
                tag = Tag(namespace=namespace,
                          public_id=canonical_name,
                          name=canonical_name,
                          user_mutable=True)
                db_session.add(tag)
        db_session.commit()

        # Add tags corresponding to existing folders
        count = 0
        for folderitem in db_session.query(FolderItem).yield_per(500):
            folderitem.thread.also_set_tag(None, folderitem, False)
            count += 1
            if not count % 500:
                db_session.commit()

        db_session.commit()


def downgrade():
    # TOO HARD
    raise Exception("Not supported.")
