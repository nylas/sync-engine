"""Store passwords in plaintext.

Revision ID: 7a117720554
Revises: 247cd689758c
Create Date: 2014-06-30 20:36:30.705550

"""

# revision identifiers, used by Alembic.
revision = '7a117720554'
down_revision = '247cd689758c'

import os
from alembic import op
import sqlalchemy as sa

# We're deleting this value from the config, so need to explicitly give it for
# this migration.
# If you're running this migration and for some reason you had specified a
# different key directory, you should change this accordingly.
KEY_DIR = '/var/lib/inboxapp/keys'


# Copied from deprecated inbox.util.cryptography module.
# Needed to port passwords to new storage method.
def decrypt_aes(ciphertext, key):
    """
    Decrypts a ciphertext that was AES-encrypted with the given key.
    The function expects the ciphertext as a byte string and it returns the
    decrypted message as a byte string.
    """
    from Crypto.Cipher import AES
    unpad = lambda s: s[:-ord(s[-1])]
    iv = ciphertext[:AES.block_size]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(ciphertext))[AES.block_size:]
    return plaintext


def upgrade():
    from inbox.models.session import session_scope
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    from inbox.util.file import mkdirp
    from hashlib import sha256

    OriginalBase = sa.ext.declarative.declarative_base()
    OriginalBase.metadata.reflect(engine)

    if 'easaccount' in OriginalBase.metadata.tables:
        op.add_column('easaccount', sa.Column('password', sa.String(256)))

        # Reflect again to pick up added column
        Base = sa.ext.declarative.declarative_base()
        Base.metadata.reflect(engine)

        class Account(Base):
            __table__ = Base.metadata.tables['account']

        class EASAccount(Account):
            __table__ = Base.metadata.tables['easaccount']

            @property
            def _keyfile(self, create_dir=True):
                assert self.key

                assert KEY_DIR
                if create_dir:
                    mkdirp(KEY_DIR)
                key_filename = '{0}'.format(sha256(self.key).hexdigest())
                return os.path.join(KEY_DIR, key_filename)

            def get_old_password(self):
                if self.password_aes is not None:
                    with open(self._keyfile, 'r') as f:
                        key = f.read()

                    key = self.key + key
                    return decrypt_aes(self.password_aes, key)

        with session_scope() as db_session:
            for account in db_session.query(EASAccount):
                account.password = account.get_old_password()
                db_session.add(account)
            db_session.commit()

    op.drop_column('account', 'password_aes')
    op.drop_column('account', 'key')


def downgrade():
    raise Exception('No rolling back')
