"""gmailaccount

Revision ID: 4085dd542739
Revises: 1c72d8a0120e
Create Date: 2014-06-17 22:48:01.928601

"""

# revision identifiers, used by Alembic.
revision = '4085dd542739'
down_revision = '1c72d8a0120e'

from alembic import op
import sqlalchemy as sa


def upgrade():

    print 'Creating new table gmailaccount'

    op.create_table(
        'gmailaccount',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('access_token', sa.String(length=512), nullable=True),
        sa.Column('refresh_token', sa.String(length=512), nullable=True),
        sa.Column('scope', sa.String(length=512), nullable=True),
        sa.Column('expires_in', sa.Integer(), nullable=True),
        sa.Column('token_type', sa.String(length=64), nullable=True),
        sa.Column('access_type', sa.String(length=64), nullable=True),
        sa.Column('family_name', sa.String(length=256), nullable=True),
        sa.Column('given_name', sa.String(length=256), nullable=True),
        sa.Column('name', sa.String(length=256), nullable=True),
        sa.Column('gender', sa.String(length=16), nullable=True),
        sa.Column('g_id', sa.String(length=32), nullable=True),
        sa.Column('g_id_token', sa.String(length=1024), nullable=True),
        sa.Column('g_user_id', sa.String(length=32), nullable=True),
        sa.Column('link', sa.String(length=256), nullable=True),
        sa.Column('locale', sa.String(length=8), nullable=True),
        sa.Column('picture', sa.String(length=1024), nullable=True),
        sa.Column('home_domain', sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['imapaccount.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    from sqlalchemy.ext.declarative import declarative_base
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    from inbox.models.session import session_scope

    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Account(Base):
        __table__ = Base.metadata.tables['account']

    class ImapAccount(Base):
        __table__ = Base.metadata.tables['imapaccount']

    class GmailAccount(Base):
        __table__ = Base.metadata.tables['gmailaccount']

    with session_scope(versioned=False) as db_session:
        for acct in db_session.query(Account):
            if acct.provider == 'Gmail':
                imap_acct = db_session.query(ImapAccount). \
                    filter_by(id=acct.id).one()
                gmail_acct = GmailAccount(id=acct.id,
                                          access_token=acct.o_access_token,
                                          refresh_token=acct.o_refresh_token,
                                          scope=acct.o_scope,
                                          expires_in=acct.o_expires_in,
                                          token_type=acct.o_token_type,
                                          access_type=acct.o_access_type,
                                          family_name=imap_acct.family_name,
                                          given_name=imap_acct.given_name,
                                          name=None,
                                          gender=imap_acct.g_gender,
                                          g_id=imap_acct.google_id,
                                          g_id_token=acct.o_id_token,
                                          g_user_id=acct.o_user_id,
                                          link=imap_acct.g_plus_url,
                                          locale=imap_acct.g_locale,
                                          picture=imap_acct.g_picture_url,
                                          home_domain=None
                                          )
                acct.type = 'gmailaccount'
                db_session.add(gmail_acct)
        db_session.commit()

    op.drop_column('account', u'o_access_token')
    op.drop_column('account', u'o_audience')
    op.drop_column('account', u'o_scope')
    op.drop_column('account', u'o_token_type')
    op.drop_column('account', u'o_id_token')
    op.drop_column('account', u'o_access_type')
    op.drop_column('account', u'o_expires_in')
    op.drop_column('account', u'o_user_id')
    op.drop_column('account', u'provider_prefix')
    op.drop_column('account', u'o_verified_email')
    op.drop_column('account', u'provider')
    op.drop_column('account', u'date')
    op.drop_column('account', u'o_token_issued_to')
    op.drop_column('account', u'o_refresh_token')
    op.drop_column('imapaccount', u'family_name')
    op.drop_column('imapaccount', u'google_id')
    op.drop_column('imapaccount', u'g_plus_url')
    op.drop_column('imapaccount', u'g_picture_url')
    op.drop_column('imapaccount', u'g_gender')
    op.drop_column('imapaccount', u'given_name')
    op.drop_column('imapaccount', u'g_locale')


def downgrade():
    raise Exception("Only roll forward!")
