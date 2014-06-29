""" Rename WebhookParameters -> Webhook

Note that this migration deletes old webhook data.
This is OK because we haven't stored any webhooks yet.

Revision ID: 2c313b6ddd9b
Revises: 519e462df171
Create Date: 2014-05-04 03:14:39.923489

"""

# revision identifiers, used by Alembic.
revision = '2c313b6ddd9b'
down_revision = '519e462df171'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.sqlalchemy_ext.util import Base36UID

    print "Rename WebhookParameters -> Webhook"
    op.rename_table('webhookparameters', 'webhook')

    op.drop_index('ix_webhookparameters_public_id', table_name='webhook')
    op.create_index(
        'ix_webhook_namespace_id', 'webhook', ['namespace_id'], unique=False)
    op.create_index(
        'ix_webhook_public_id', 'webhook', ['public_id'], unique=False)
    op.create_foreign_key('webhooks_ibfk_1', 'webhook', 'namespace',
                          ['namespace_id'], ['id'], ondelete='CASCADE')

    print 'Creating Lens'
    op.create_table('lens',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column(
                        'public_id', Base36UID(length=16), nullable=False),
                    sa.Column('namespace_id', sa.Integer(), nullable=False),
                    sa.Column('subject', sa.String(length=255), nullable=True),
                    sa.Column(
                        'thread_public_id',
                        Base36UID(length=16),
                        nullable=True),
                    sa.Column('started_before', sa.DateTime(), nullable=True),
                    sa.Column('started_after', sa.DateTime(), nullable=True),
                    sa.Column(
                        'last_message_before', sa.DateTime(), nullable=True),
                    sa.Column(
                        'last_message_after', sa.DateTime(), nullable=True),
                    sa.Column(
                        'any_email', sa.String(length=255), nullable=True),
                    sa.Column('to_addr', sa.String(length=255), nullable=True),
                    sa.Column(
                        'from_addr', sa.String(length=255), nullable=True),
                    sa.Column('cc_addr', sa.String(length=255), nullable=True),
                    sa.Column(
                        'bcc_addr', sa.String(length=255), nullable=True),
                    sa.Column(
                        'filename', sa.String(length=255), nullable=True),
                    sa.Column('tag', sa.String(length=255), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['namespace_id'],
                        ['namespace.id'],
                        ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )

    op.create_index(
        'ix_lens_namespace_id', 'lens', ['namespace_id'], unique=False)
    op.create_index('ix_lens_public_id', 'lens', ['public_id'], unique=False)

    print 'Removing old webhooks'
    op.add_column(
        u'webhook', sa.Column('lens_id', sa.Integer(), nullable=False))

    op.drop_column(u'webhook', u'last_message_after')
    op.drop_column(u'webhook', u'last_message_before')
    op.drop_column(u'webhook', u'thread')
    op.drop_column(u'webhook', u'from_addr')
    op.drop_column(u'webhook', u'started_after')
    op.drop_column(u'webhook', u'to_addr')
    op.drop_column(u'webhook', u'filename')
    op.drop_column(u'webhook', u'bcc_addr')
    op.drop_column(u'webhook', u'cc_addr')
    op.drop_column(u'webhook', u'started_before')
    op.drop_column(u'webhook', u'email')
    op.drop_column(u'webhook', u'subject')

    op.create_index('ix_webhook_lens_id', 'webhook', ['lens_id'], unique=False)


def downgrade():
    raise Exception("Nope.")
