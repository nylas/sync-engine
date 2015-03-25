"""revert account unique constraint

Revision ID: 4032709362da
Revises: 211e93aff1e1
Create Date: 2015-03-25 23:46:25.649192

"""

# revision identifiers, used by Alembic.
revision = '4032709362da'
down_revision = '211e93aff1e1'

from alembic import op


def upgrade():
    conn = op.get_bind()
    index_name = conn.execute(
        '''SELECT index_name FROM information_schema.statistics WHERE
           table_name="account" AND non_unique=0 AND
           column_name="_canonicalized_address"''').fetchone()[0]
    op.drop_constraint(index_name, 'account', type_='unique')
    if index_name == 'ix_account__canonicalized_address':
        op.create_index('ix_account__canonicalized_address', 'account',
                        ['_canonicalized_address'], unique=False)


def downgrade():
    op.create_unique_constraint('unique_account_address', 'account',
                                ['_canonicalized_address'])
