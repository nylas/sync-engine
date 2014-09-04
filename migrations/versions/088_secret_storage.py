"""Secret storage

Revision ID: 1683790906cf
Revises: 4e3e8abea884
Create Date: 2014-08-20 00:42:10.269746

"""

# revision identifiers, used by Alembic.
revision = '1683790906cf'
down_revision = '565c7325c51d'

from alembic import op
import sqlalchemy as sa
import nacl.secret
import nacl.utils


def upgrade():
    # Can just drop this, was't really used before
    op.drop_column('secret', 'acl_id')

    op.alter_column('secret', 'type', type_=sa.Enum('password', 'token'),
                    existing_server_default=None,
                    existing_nullable=False)
    op.add_column('secret', sa.Column('encryption_scheme', sa.Integer(),
                  server_default='0', nullable=False))

    # Change name, type
    op.add_column('secret', sa.Column('_secret', sa.BLOB(),
                                      nullable=False))

    from inbox.ignition import main_engine
    from inbox.models.session import session_scope
    from inbox.config import config
    from inbox.models.util import EncryptionScheme

    engine = main_engine(pool_size=1, max_overflow=0)
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)

    class Secret(Base):
        __table__ = Base.metadata.tables['secret']

    with session_scope(ignore_soft_deletes=False, versioned=False) as \
            db_session:
        secrets = db_session.query(Secret).filter(
            Secret.secret.isnot(None)).all()

        for s in secrets:
            plain = s.secret.encode('ascii') if isinstance(s.secret, unicode) \
                else s.secret

            s._secret = nacl.secret.SecretBox(
                key=config.get_required('SECRET_ENCRYPTION_KEY'),
                encoder=nacl.encoding.HexEncoder
            ).encrypt(
                plaintext=plain,
                nonce=nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE))

            s.encryption_scheme = EncryptionScheme.SECRETBOX_WITH_STATIC_KEY

            # Picked arbitrarily
            s.type = 'password'

            db_session.add(s)

        db_session.commit()

    op.drop_column('secret', 'secret')


def downgrade():
    raise Exception('No.')
