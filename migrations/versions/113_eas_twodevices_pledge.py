"""EAS two-devices pledge

Revision ID: ad7b856bcc0
Revises: 22d076f48b88
Create Date: 2014-10-20 17:31:52.121360

"""

# revision identifiers, used by Alembic.
revision = 'ad7b856bcc0'
down_revision = '26911668870a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine()

    if not engine.has_table('easaccount'):
        return

    op.create_table('easdevice',
                    sa.Column('created_at', sa.DateTime(), nullable=True),
                    sa.Column('updated_at', sa.DateTime(), nullable=True),
                    sa.Column('deleted_at', sa.DateTime(), nullable=True),
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('filtered', sa.Boolean(), nullable=False),
                    sa.Column('eas_device_id', sa.String(length=32),
                              nullable=False),
                    sa.Column('eas_device_type', sa.String(length=32),
                              nullable=False),
                    sa.Column('eas_policy_key', sa.String(length=64),
                              nullable=True),
                    sa.Column('eas_sync_key', sa.String(length=64),
                              server_default='0', nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_easdevice_created_at', 'easdevice', ['created_at'],
                    unique=False)
    op.create_index('ix_easdevice_updated_at', 'easdevice', ['updated_at'],
                    unique=False)
    op.create_index('ix_easdevice_deleted_at', 'easdevice', ['deleted_at'],
                    unique=False)
    op.create_index('ix_easdevice_eas_device_id', 'easdevice',
                    ['eas_device_id'], unique=False)

    op.add_column('easaccount', sa.Column('primary_device_id', sa.Integer(),
                                          sa.ForeignKey('easdevice.id'),
                                          nullable=True))
    op.add_column('easaccount', sa.Column('secondary_device_id', sa.Integer(),
                                          sa.ForeignKey('easdevice.id'),
                                          nullable=True))

    op.add_column('easfoldersyncstatus', sa.Column(
        'device_id', sa.Integer(), sa.ForeignKey(
            'easdevice.id', ondelete='CASCADE'), nullable=True))
    op.drop_constraint('account_id', 'easfoldersyncstatus',
                       type_='unique')
    op.create_unique_constraint(None, 'easfoldersyncstatus',
                                ['account_id', 'device_id', 'folder_id'])
    op.drop_constraint('easfoldersyncstatus_ibfk_1', 'easfoldersyncstatus',
                       type_='foreignkey')
    op.drop_constraint('easfoldersyncstatus_ibfk_2', 'easfoldersyncstatus',
                       type_='foreignkey')
    op.drop_constraint('account_id_2', 'easfoldersyncstatus',
                       type_='unique')
    op.create_foreign_key('easfoldersyncstatus_ibfk_1', 'easfoldersyncstatus',
                          'easaccount', ['account_id'], ['id'])
    op.create_foreign_key('easfoldersyncstatus_ibfk_2', 'easfoldersyncstatus',
                          'folder', ['folder_id'], ['id'])
    op.create_unique_constraint(None, 'easfoldersyncstatus',
                                ['account_id', 'device_id', 'eas_folder_id'])

    op.add_column(
        'easuid', sa.Column('device_id', sa.Integer(), sa.ForeignKey(
            'easdevice.id', ondelete='CASCADE'), nullable=True))
    op.drop_constraint('easuid_ibfk_3', 'easuid', type_='foreignkey')
    op.drop_constraint('folder_id', 'easuid', type_='unique')
    op.create_foreign_key('easuid_ibfk_3', 'easuid', 'folder',
                          ['folder_id'], ['id'])
    op.create_unique_constraint(
        None, 'easuid', ['folder_id', 'msg_uid', 'easaccount_id', 'device_id'])


def downgrade():
    raise Exception('!')
