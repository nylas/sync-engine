"""add reply_to_message_id

Revision ID: 1d7a72222b7c
Revises:2d8a350b4885
Create Date: 2015-02-18 21:40:50.082303

"""

# revision identifiers, used by Alembic.
revision = '1d7a72222b7c'
down_revision = '2d8a350b4885'

from alembic import op


def upgrade():
    conn = op.get_bind()
    # This rigamarole is only necessary in MySQL 5.5. In MySQL 5.6 you can just
    # change the column name.

    # The constraint name might be `message_ibfk_2` or `message_ibfk_3` or
    # whatever, so figure out which it is first.
    constraint_name = conn.execute(
        '''SELECT constraint_name FROM information_schema.key_column_usage
           WHERE table_name='message' AND referenced_table_name='message'
           AND constraint_schema=DATABASE()''').fetchone()[0]
    conn.execute('ALTER TABLE message DROP FOREIGN KEY {}'.format(constraint_name))
    conn.execute('ALTER TABLE message CHANGE resolved_message_id reply_to_message_id INT(11)')
    conn.execute('ALTER TABLE message ADD CONSTRAINT {} FOREIGN KEY (reply_to_message_id) REFERENCES message(id)'.
                 format(constraint_name))


def downgrade():
    conn = op.get_bind()
    constraint_name = conn.execute(
        '''SELECT constraint_name FROM information_schema.key_column_usage
           WHERE table_name='message' AND referenced_table_name='message'
           AND constraint_schema=DATABASE()''').fetchone()[0]
    conn.execute('ALTER TABLE message DROP FOREIGN KEY {}'.format(constraint_name))
    conn.execute('ALTER TABLE message DROP FOREIGN KEY message_ibfk_3')
    conn.execute('ALTER TABLE message CHANGE reply_to_message_id resolved_message_id INT(11)')
    conn.execute('ALTER TABLE message ADD CONSTRAINT {} FOREIGN KEY (resolved_message_id) REFERENCES message(id)'.
                 format(constraint_name))
