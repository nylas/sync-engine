"""Secret storage

Revision ID: 1683790906cf
Revises427812c1e849:
Create Date: 2014-08-20 00:42:10.269746

"""

# revision identifiers, used by Alembic.
revision = '1683790906cf'
down_revision = '427812c1e849'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # SECRETS TABLE:
    # Can just drop this, was't really used before
    op.drop_column('secret', 'acl_id')

    op.alter_column('secret', 'type', type_=sa.Enum('password', 'token'),
                    existing_server_default=None,
                    existing_nullable=False)

    op.add_column('secret', sa.Column('encryption_scheme', sa.Integer(),
                  server_default='0', nullable=False))
    op.add_column('secret', sa.Column('_secret', sa.BLOB(),
                                      nullable=False))

    # Account tables:
    # Don't need to change column types for password_id, refresh_token_id;
    # only add foreign key indices.
    op.create_foreign_key('genericaccount_ibfk_2', 'genericaccount', 'secret',
                          ['password_id'], ['id'])
    op.create_foreign_key('gmailaccount_ibfk_2', 'gmailaccount', 'secret',
                          ['refresh_token_id'], ['id'])
    op.create_foreign_key('outlookaccount_ibfk_2', 'outlookaccount', 'secret',
                          ['refresh_token_id'], ['id'])


def downgrade():
    raise Exception()
