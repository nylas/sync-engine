"""migrate_secret_data

Revision ID: 38c29430efeb
Revises: 1683790906cf
Create Date: 2014-09-18 03:03:42.131932

"""

# revision identifiers, used by Alembic.
revision = '38c29430efeb'
down_revision = '1683790906cf'

import sqlalchemy as sa


def upgrade():
    from inbox.config import config
    import nacl.secret
    import nacl.utils
    from inbox.ignition import main_engine
    from inbox.models.session import session_scope

    engine = main_engine(pool_size=1, max_overflow=0)
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)

    class Secret(Base):
        __table__ = Base.metadata.tables['secret']

    class GenericAccount(Base):
        __table__ = Base.metadata.tables['genericaccount']

    with session_scope(versioned=False) as \
            db_session:
        secrets = db_session.query(Secret).filter(
            Secret.secret.isnot(None)).all()

        # Join on the genericaccount and optionally easaccount tables to
        # determine which secrets should have type 'password'.
        generic_query = db_session.query(Secret.id).join(
            GenericAccount).filter(Secret.id == GenericAccount.password_id)
        password_secrets = [id_ for id_, in generic_query]
        if engine.has_table('easaccount'):
            class EASAccount(Base):
                __table__ = Base.metadata.tables['easaccount']

            eas_query = db_session.query(Secret.id).join(
                EASAccount).filter(Secret.id == EASAccount.password_id)
            password_secrets.extend([id_ for id_, in eas_query])

        for s in secrets:
            plain = s.secret.encode('utf-8') if isinstance(s.secret, unicode) \
                else s.secret
            if config.get_required('ENCRYPT_SECRETS'):

                s._secret = nacl.secret.SecretBox(
                    key=config.get_required('SECRET_ENCRYPTION_KEY'),
                    encoder=nacl.encoding.HexEncoder
                ).encrypt(
                    plaintext=plain,
                    nonce=nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE))

                # 1 is EncryptionScheme.SECRETBOX_WITH_STATIC_KEY
                s.encryption_scheme = 1
            else:
                s._secret = plain

            if s.id in password_secrets:
                s.type = 'password'
            else:
                s.type = 'token'

            db_session.add(s)

        db_session.commit()


def downgrade():
    pass
