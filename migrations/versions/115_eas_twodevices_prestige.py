"""EAS two-devices prestige

Revision ID: 10ecf4841ac3
Revises: 17dc9c049f8b
Create Date: 2014-10-21 20:38:17.143065

"""

# revision identifiers, used by Alembic.
revision = '10ecf4841ac3'
down_revision = '17dc9c049f8b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('easdevice', 'created_at',
                    existing_type=sa.DateTime(), nullable=False)
    op.alter_column('easdevice', 'updated_at',
                    existing_type=sa.DateTime(), nullable=False)
    op.alter_column('easaccount', 'primary_device_id',
                    existing_type=sa.Integer(), nullable=False)
    op.alter_column('easaccount', 'secondary_device_id',
                    existing_type=sa.Integer(), nullable=False)
    op.alter_column('easfoldersyncstatus', 'device_id',
                    existing_type=sa.Integer(), nullable=False)
    op.alter_column('easuid', 'device_id',
                    existing_type=sa.Integer(), nullable=False)

    op.drop_column('easaccount', '_eas_device_type')
    op.drop_column('easaccount', '_eas_device_id')
    op.drop_column('easaccount', 'eas_policy_key')
    op.drop_column('easaccount', 'eas_account_sync_key')


def downgrade():
    raise Exception('!')
