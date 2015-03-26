"""add message indices

Revision ID: 1f06c15ae796
Revises: 4032709362da
Create Date: 2015-03-26 21:54:13.037161

"""

# revision identifiers, used by Alembic.
revision = '1f06c15ae796'
down_revision = '4032709362da'

from alembic import op


def upgrade():
    conn = op.get_bind()
    data_sha256_index_exists = conn.execute(
        '''SELECT COUNT(*) FROM information_schema.statistics WHERE
           table_name="message" AND
           column_name="data_sha256"''').fetchone()[0]
    if not data_sha256_index_exists:
        conn.execute(
            '''ALTER TABLE message
               ADD INDEX `ix_message_data_sha256` (`data_sha256`(191))''')

    received_date_index_exists = conn.execute(
        '''SELECT COUNT(*) FROM information_schema.statistics WHERE
           table_name="message" AND
           column_name="received_date"''').fetchone()[0]
    if not received_date_index_exists:
        conn.execute(
            '''ALTER TABLE message
               ADD INDEX `ix_message_received_date` (`received_date`)''')


def downgrade():
    raise Exception()
