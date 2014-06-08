"""Move Google UserInfo fields to ImapAccount table

Revision ID: 193802835c33
Revises: 169cac0cd87e
Create Date: 2014-04-15 02:21:13.398192

"""

# revision identifiers, used by Alembic.
revision = '193802835c33'
down_revision = '3237b6b1ee03'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.sql import table, column, text
from sqlalchemy.ext.declarative import declarative_base

from inbox.models import session_scope
from inbox.models.ignition import engine

Base = declarative_base()
Base.metadata.reflect(engine)


def upgrade():
    # ADD:
    op.add_column('imapaccount', sa.Column('family_name', sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('g_gender', sa.String(length=16),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('g_locale', sa.String(length=16),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('g_picture_url', sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('g_plus_url', sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('given_name', sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('google_id', sa.String(length=255),
                                           nullable=True))

    # MOVE:
    class Account_(Base):
        __table__ = Base.metadata.tables['account']

    with session_scope() as db_session:
        results = db_session.query(Account_.id,
                                   Account_.family_name,
                                   Account_.google_id,
                                   Account_.g_plus_url,
                                   Account_.g_picture_url,
                                   Account_.g_gender,
                                   Account_.given_name,
                                   Account_.g_locale).all()

    imapaccount = table('imapaccount',
                        column('id', sa.String),
                        column('family_name', sa.String),
                        column('google_id', sa.String),
                        column('g_plus_url', sa.String),
                        column('g_picture_url', sa.String),
                        column('g_gender', sa.String),
                        column('given_name', sa.String),
                        column('g_locale', sa.String))

    for r in results:
        op.execute(
          imapaccount.update().where(imapaccount.c.id==r[0]).values({
            'family_name': r[1],
            'google_id': r[2],
            'g_plus_url': r[3],
            'g_picture_url': r[4],
            'g_gender': r[5],
            'given_name': r[6],
            'g_locale': r[7]
          })
        )

    # DROP:
    op.drop_column('account', 'family_name')
    op.drop_column('account', 'google_id')
    op.drop_column('account', 'g_plus_url')
    op.drop_column('account', 'g_picture_url')
    op.drop_column('account', 'g_gender')
    op.drop_column('account', 'given_name')
    op.drop_column('account', 'g_locale')


def downgrade():
    # ADD:
    op.add_column('account', sa.Column('family_name', sa.String(length=255),
                                       nullable=True))
    op.add_column('account', sa.Column('g_gender', sa.String(length=16),
                                       nullable=True))
    op.add_column('account', sa.Column('g_locale', sa.String(length=16),
                                       nullable=True))
    op.add_column('account', sa.Column('g_picture_url', sa.String(length=255),
                                       nullable=True))
    op.add_column('account', sa.Column('g_plus_url', sa.String(length=255),
                                       nullable=True))
    op.add_column('account', sa.Column('given_name', sa.String(length=255),
                                       nullable=True))
    op.add_column('account', sa.Column('google_id', sa.String(length=255),
                                       nullable=True))

    # MOVE:
    class ImapAccount_(Base):
        __table__ = Base.metadata.tables['imapaccount']

    with session_scope() as db_session:
        results = db_session.query(ImapAccount_.id,
                                   ImapAccount_.family_name,
                                   ImapAccount_.google_id,
                                   ImapAccount_.g_plus_url,
                                   ImapAccount_.g_picture_url,
                                   ImapAccount_.g_gender,
                                   ImapAccount_.given_name,
                                   ImapAccount_.g_locale).all()

    account = table('account',
                    column('id', sa.String),
                    column('family_name', sa.String),
                    column('google_id', sa.String),
                    column('g_plus_url', sa.String),
                    column('g_picture_url', sa.String),
                    column('g_gender', sa.String),
                    column('given_name', sa.String),
                    column('g_locale', sa.String))

    for r in results:
        op.execute(
          account.update().where(account.c.id==r[0]).values({
            'family_name': r[1],
            'google_id': r[2],
            'g_plus_url': r[3],
            'g_picture_url': r[4],
            'g_gender': r[5],
            'given_name': r[6],
            'g_locale': r[7]
          })
        )

    # DROP:
    op.drop_column('imapaccount', 'family_name')
    op.drop_column('imapaccount', 'google_id')
    op.drop_column('imapaccount', 'g_plus_url')
    op.drop_column('imapaccount', 'g_picture_url')
    op.drop_column('imapaccount', 'g_gender')
    op.drop_column('imapaccount', 'given_name')
    op.drop_column('imapaccount', 'g_locale')
