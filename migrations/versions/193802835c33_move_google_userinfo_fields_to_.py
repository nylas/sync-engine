"""Move Google UserInfo fields to ImapAccount table

Revision ID: 193802835c33
Revises: 169cac0cd87e
Create Date: 2014-04-15 02:21:13.398192

"""

# revision identifiers, used by Alembic.
revision = '193802835c33'
down_revision = '169cac0cd87e'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.drop_column('account', u'family_name')
    op.drop_column('account', u'google_id')
    op.drop_column('account', u'g_plus_url')
    op.drop_column('account', u'g_picture_url')
    op.drop_column('account', u'g_gender')
    op.drop_column('account', u'given_name')
    op.drop_column('account', u'g_locale')

    op.add_column('imapaccount', sa.Column('family_name',
                                           sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('g_gender',
                                           sa.String(length=16),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('g_locale',
                                           sa.String(length=16),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('g_picture_url',
                                           sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('g_plus_url',
                                           sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('given_name',
                                           sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('google_id',
                                           sa.String(length=255),
                                           nullable=True))


def downgrade():
    op.drop_column('imapaccount', 'google_id')
    op.drop_column('imapaccount', 'given_name')
    op.drop_column('imapaccount', 'g_plus_url')
    op.drop_column('imapaccount', 'g_picture_url')
    op.drop_column('imapaccount', 'g_locale')
    op.drop_column('imapaccount', 'g_gender')
    op.drop_column('imapaccount', 'family_name')

    op.add_column('account', sa.Column(u'g_locale',
                                       mysql.VARCHAR(length=16),
                                       nullable=True))
    op.add_column('account', sa.Column(u'given_name',
                                       mysql.VARCHAR(length=255),
                                       nullable=True))
    op.add_column('account', sa.Column(u'g_gender',
                                       mysql.VARCHAR(length=16),
                                       nullable=True))
    op.add_column('account', sa.Column(u'g_picture_url',
                                       mysql.VARCHAR(length=255),
                                       nullable=True))
    op.add_column('account', sa.Column(u'g_plus_url',
                                       mysql.VARCHAR(length=255),
                                       nullable=True))
    op.add_column('account', sa.Column(u'google_id',
                                       mysql.VARCHAR(length=255),
                                       nullable=True))
    op.add_column('account', sa.Column(u'family_name',
                                       mysql.VARCHAR(length=255),
                                       nullable=True))
