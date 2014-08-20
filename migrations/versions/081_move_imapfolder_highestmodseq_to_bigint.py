"""move imapfolder highestmodseq to bigint

Revision ID: 1bc2536b8bc6
Revises: 4e3e8abea884
Create Date: 2014-08-18 18:57:29.833221

"""

# revision identifiers, used by Alembic.
revision = '1bc2536b8bc6'
down_revision = '4e3e8abea884'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('imapfolderinfo', 'highestmodseq',
                    type_=sa.BigInteger, existing_type=sa.Integer,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=True)

    op.alter_column('imapfolderinfo', 'uidvalidity',
                    type_=sa.BigInteger, existing_type=sa.Integer,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=True)


def downgrade():
    pass
