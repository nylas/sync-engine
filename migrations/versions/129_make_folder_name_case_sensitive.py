"""Make folder.name case sensitive.

Revision ID: 5349c1a03fde
Revises: 284227d72f51
Create Date: 2015-01-23 10:07:26.090495

"""

# revision identifiers, used by Alembic.
revision = '5349c1a03fde'
down_revision = '284227d72f51'

from alembic import op


def upgrade():
    connection = op.get_bind()
    connection.execute(
        '''
        ALTER TABLE folder CHANGE name name varchar(191) BINARY DEFAULT NULL;
        '''
    )


def downgrade():
    connection = op.get_bind()
    connection.execute(
        '''
        ALTER TABLE folder CHANGE name name varchar(191) DEFAULT NULL;
        '''
    )
