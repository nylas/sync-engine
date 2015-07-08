"""backfill_gmail_auth_credentials_table

Revision ID: 14692efd261b
Revises: 2ac4e3c4e049
Create Date: 2015-07-01 00:26:38.736689

"""

# revision identifiers, used by Alembic.
revision = '14692efd261b'
down_revision = '2ac4e3c4e049'


def upgrade():
    import datetime
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import relationship
    from inbox.config import config
    from inbox.models.session import session_scope
    from inbox.ignition import main_engine
    engine = main_engine()

    now = datetime.datetime.now()
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class GmailAccount(Base):
        __table__ = Base.metadata.tables['gmailaccount']

    class Secret(Base):
        __table__ = Base.metadata.tables['secret']

    class GmailAuthCredentials(Base):
        __table__ = Base.metadata.tables['gmailauthcredentials']
        secret = relationship(Secret)

    with session_scope(versioned=False) as db_session:

        for acc, sec in db_session.query(GmailAccount, Secret) \
                        .filter(GmailAccount.refresh_token_id == Secret.id,
                                GmailAccount.scope != None,
                                GmailAccount.g_id_token != None) \
                        .all():

            # Create a new GmailAuthCredentials entry if
            # we don't have one already
            if db_session.query(GmailAuthCredentials, Secret) \
                    .filter(GmailAuthCredentials.gmailaccount_id == acc.id) \
                    .filter(Secret._secret == sec._secret) \
                    .count() == 0:

                # Create a new secret
                new_sec = Secret()
                new_sec.created_at = now
                new_sec.updated_at = now
                new_sec._secret = sec._secret
                new_sec.type = sec.type  # 'token'
                new_sec.encryption_scheme = sec.encryption_scheme

                # Create a new GmailAuthCredentials entry
                auth_creds = GmailAuthCredentials()
                auth_creds.gmailaccount_id = acc.id
                auth_creds.scopes = acc.scope
                auth_creds.g_id_token = acc.g_id_token
                auth_creds.created_at = now
                auth_creds.updated_at = now
                auth_creds.secret = new_sec

                auth_creds.client_id = \
                    (acc.client_id or
                     config.get_required('GOOGLE_OAUTH_CLIENT_ID'))

                auth_creds.client_secret = \
                    (acc.client_secret or
                     config.get_required('GOOGLE_OAUTH_CLIENT_SECRET'))

                db_session.add(auth_creds)
                db_session.add(new_sec)

        db_session.commit()


def downgrade():
    pass
