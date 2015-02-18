"""Add compound index to Contact and Event

Revision ID: 1fd7b3e0b662
Revises: 5305d4ae30b4
Create Date: 2015-02-17 18:11:30.726188

"""

# revision identifiers, used by Alembic.
revision = '1fd7b3e0b662'
down_revision = '5305d4ae30b4'

from alembic import op


def upgrade():
    op.create_index(
        'ix_contact_ns_uid_provider_name',
        'contact',
        ['namespace_id', 'uid', 'provider_name'], unique=False)

    op.create_index(
        'ix_event_ns_uid_provider_name',
        'event',
        ['namespace_id', 'uid', 'provider_name'], unique=False)


def downgrade():
    raise Exception("Don't bother.")
