"""Add columns for smtp/imap-specific auth

Revision ID: 501f6b2fef28
Revises: 3618838f5bc6
Create Date: 2016-01-29 00:27:08.174534

"""

# revision identifiers, used by Alembic.
revision = '501f6b2fef28'
down_revision = '3618838f5bc6'

from alembic import op, context
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("set @@foreign_key_checks = 0;"))

    # Add new columns + ForeignKey constraints.
    shard_id = int(context.get_x_argument(as_dictionary=True).get('shard_id'))
    if shard_id == 0:
        conn.execute(text("ALTER TABLE genericaccount "
                          "ADD COLUMN imap_username CHAR(255) DEFAULT NULL, "
                          "ADD COLUMN smtp_username CHAR(255) DEFAULT NULL, "
                          "ADD COLUMN imap_password_id INT(11), "
                          "ADD COLUMN smtp_password_id INT(11), "
                          "ADD CONSTRAINT imap_password_id_ifbk FOREIGN KEY "
                          "(`imap_password_id`) REFERENCES `secret` (`id`), "
                          "ADD CONSTRAINT smtp_password_id_ifbk FOREIGN KEY "
                          "(`smtp_password_id`) REFERENCES `secret` (`id`);"))
    else:
        conn.execute(text("ALTER TABLE genericaccount "
                          "ADD COLUMN imap_username CHAR(255) DEFAULT NULL, "
                          "ADD COLUMN smtp_username CHAR(255) DEFAULT NULL, "
                          "ADD COLUMN imap_password_id BIGINT(20), "
                          "ADD COLUMN smtp_password_id BIGINT(20), "
                          "ADD CONSTRAINT imap_password_id_ifbk FOREIGN KEY "
                          "(`imap_password_id`) REFERENCES `secret` (`id`), "
                          "ADD CONSTRAINT smtp_password_id_ifbk FOREIGN KEY "
                          "(`smtp_password_id`) REFERENCES `secret` (`id`);"))


def downgrade():
    pass
