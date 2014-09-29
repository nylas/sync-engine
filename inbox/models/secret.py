from sqlalchemy import Column, Enum, Integer
from sqlalchemy.types import BLOB
from sqlalchemy.orm import validates

from inbox.models.base import MailSyncBase
from inbox.security.oracles import get_encryption_oracle, get_decryption_oracle


class Secret(MailSyncBase):
    """Simple local secrets table."""
    _secret = Column(BLOB, nullable=False)

    # Type of secret
    type = Column(Enum('password', 'token'), nullable=False)

    # Scheme used
    encryption_scheme = Column(Integer, server_default='0', nullable=False)

    @property
    def secret(self):
        with get_decryption_oracle('SECRET_ENCRYPTION_KEY') as d_oracle:
            return d_oracle.decrypt(
                self._secret,
                encryption_scheme=self.encryption_scheme)

    @secret.setter
    def secret(self, plaintext):
        """
        The secret must be a byte sequence.
        The type must be specified as 'password'/'token'.

        """
        if not isinstance(plaintext, bytes):
            raise TypeError('Invalid secret')

        with get_encryption_oracle('SECRET_ENCRYPTION_KEY') as e_oracle:
            self._secret, self.encryption_scheme = e_oracle.encrypt(plaintext)

    @validates('type')
    def validate_type(self, k, type):
        if type != 'password' and type != 'token':
            raise TypeError('Invalid secret type: must be password or token')

        return type
