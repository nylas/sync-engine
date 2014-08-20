import nacl.secret
import nacl.utils
from sqlalchemy import Column, Enum, Integer
from sqlalchemy.types import BLOB
from sqlalchemy.orm import validates

from inbox.config import config
from inbox.models.base import MailSyncBase
from inbox.models.util import EncryptionScheme


class Secret(MailSyncBase):
    """Simple local secrets table."""
    _secret = Column(BLOB, nullable=False)

    # Type of secret
    type = Column(Enum('password', 'token'), nullable=False)

    # Scheme used
    encryption_scheme = Column(Integer, server_default='0', nullable=False)

    @property
    def secret(self):
        if self.encryption_scheme == \
                EncryptionScheme.SECRETBOX_WITH_STATIC_KEY:
            return nacl.secret.SecretBox(
                key=config.get_required('SECRET_ENCRYPTION_KEY'),
                encoder=nacl.encoding.HexEncoder
            ).decrypt(self._secret)

    @secret.setter
    def secret(self, secret):
        """
        The secret must be a byte sequence.
        The type must be specified as 'password'/'token'.

        """
        if not isinstance(secret, bytes):
            raise TypeError('Invalid secret')

        self.encryption_scheme = EncryptionScheme.SECRETBOX_WITH_STATIC_KEY

        self._secret = nacl.secret.SecretBox(
            key=config.get_required('SECRET_ENCRYPTION_KEY'),
            encoder=nacl.encoding.HexEncoder
        ).encrypt(
            plaintext=secret,
            nonce=nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE))

    @validates('type')
    def validate_type(self, k, type):
        if type != 'password' and type != 'token':
            raise TypeError('Invalid secret type: must be password or token')

        return type
