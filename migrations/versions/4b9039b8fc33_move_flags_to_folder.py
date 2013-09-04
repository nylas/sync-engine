"""Move flags to FolderMeta

Revision ID: 4b9039b8fc33
Revises: c83d87ea504
Create Date: 2013-09-03 19:08:33.524889

"""

# revision identifiers, used by Alembic.
revision = '4b9039b8fc33'
down_revision = 'c83d87ea504'

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import mysql

from sqlalchemy.sql import table, column

foldermeta = table('foldermeta', column('flags', mysql.MEDIUMBLOB),
        column('g_msgid', sa.String(255)))
messagemeta = table('messagemeta', column('flags', mysql.MEDIUMBLOB),
        column('g_msgid', sa.String(255)))


def upgrade():
    op.add_column('foldermeta', sa.Column('flags', mysql.MEDIUMBLOB))
    # copy old data to the new table before dropping old column
    # this COULD result in some bad flags but we don't care that much for
    # dev purposes. in practice, gmail may actually never have different
    # flags on different messages in different folders?
    # the update operation is suuuuper slow without this index
    op.create_index('messagemeta_g_msgid', 'messagemeta', ['g_msgid'])
    op.execute(
        foldermeta.update().values({foldermeta.c.flags: messagemeta.c.flags})\
            .where(foldermeta.c.g_msgid==messagemeta.c.g_msgid))
    op.drop_column('messagemeta', 'flags')


def downgrade():
    op.add_column('messagemeta', sa.Column('flags', mysql.MEDIUMBLOB))
    op.create_index('messagemeta_g_msgid', 'messagemeta', ['g_msgid'])
    # copy old data to the new table before dropping old column
    op.execute(
        messagemeta.update().values({messagemeta.c.flags: foldermeta.c.flags})\
            .where(messagemeta.c.g_msgid==foldermeta.c.g_msgid))
    op.drop_column('foldermeta', 'flags')
    op.drop_index('messagemeta_g_msgid')
