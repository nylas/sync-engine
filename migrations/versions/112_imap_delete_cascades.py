"""imap delete cascades

Revision ID: 26911668870a
Revises: 22d076f48b88
Create Date: 2014-10-20 22:06:33.118656

"""

# revision identifiers, used by Alembic.
revision = '26911668870a'
down_revision = '22d076f48b88'

from alembic import op


def upgrade():
    conn = op.get_bind()
    conn.execute('''
        ALTER TABLE imapfolderinfo DROP FOREIGN KEY imapfolderinfo_ibfk_2,
        ADD FOREIGN KEY (folder_id) REFERENCES folder (id) ON DELETE
        CASCADE''')

    conn.execute('''
        ALTER TABLE imapfoldersyncstatus DROP FOREIGN KEY
        imapfoldersyncstatus_ibfk_2,
        ADD FOREIGN KEY (folder_id) REFERENCES folder (id) ON DELETE
        CASCADE''')


def downgrade():
    raise Exception()
