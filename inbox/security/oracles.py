from __future__ import absolute_import, division, print_function

import enum
import nacl.secret
import nacl.utils

from inbox.config import config


class EncryptionScheme(enum.Enum):
    # No encryption
    NULL = 0

    # nacl.secret.SecretBox with a static key
    SECRETBOX_WITH_STATIC_KEY = 1


def get_encryption_oracle(secret_name):
    """
    Return an encryption oracle for the given secret.
    """
    assert secret_name in ('SECRET_ENCRYPTION_KEY', 'BLOCK_ENCRYPTION_KEY')
    return _EncryptionOracle(secret_name)


def get_decryption_oracle(secret_name):
    """
    Return an decryption oracle for the given secret.

    Decryption oracles can also encrypt.
    """
    assert secret_name in ('SECRET_ENCRYPTION_KEY', 'BLOCK_ENCRYPTION_KEY')
    return _DecryptionOracle(secret_name)


class _EncryptionOracle(object):
    """
    This object is responsible for encryption only.

    In the future, it may interface with a subprocess or a hardware security
    module.
    """

    def __init__(self, secret_name):
        self._closed = False

        if not config.get_required('ENCRYPT_SECRETS'):
            self.default_scheme = EncryptionScheme.NULL
            self._secret_box = None
            return

        self.default_scheme = EncryptionScheme.SECRETBOX_WITH_STATIC_KEY
        self._secret_box = nacl.secret.SecretBox(
            key=config.get_required(secret_name),
            encoder=nacl.encoding.HexEncoder)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_obj, exc_tb):
        self.close()

    def __del__(self):
        if self._closed:
            return
        self.close()

    def close(self):
        if self._closed:
            # already closed
            return

        del self.default_scheme
        del self._secret_box
        self._closed = 1

    def encrypt(self, plaintext, encryption_scheme=None):
        """
        Encrypt the specified secret.  If no encryption_scheme is specified
        (recommended), a reasonable default will be used.

        Returns (ciphertext, encryption_scheme)
        """
        if self._closed:
            raise ValueError("Connection to crypto oracle already closed")

        # default args
        if encryption_scheme is None:
            encryption_scheme = self.default_scheme

        # sanity check
        if isinstance(plaintext, unicode):
            raise TypeError("plaintext should be bytes, not unicode")
        if not isinstance(encryption_scheme, (int, long)):
            raise TypeError("encryption_scheme should be an integer")
        if not 0 <= encryption_scheme <= 2**31-1:
            raise ValueError("encryption_scheme out of range")
        if (encryption_scheme != EncryptionScheme.NULL and
                not config.get_required('ENCRYPT_SECRETS')):
            raise ValueError("ENCRYPT_SECRETS not enabled in config")

        # encrypt differently depending on the scheme
        if encryption_scheme == EncryptionScheme.NULL:
            ciphertext = plaintext

        elif encryption_scheme == EncryptionScheme.SECRETBOX_WITH_STATIC_KEY:
            ciphertext = self._secret_box.encrypt(
                plaintext=plaintext,
                nonce=nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE))

        else:
            raise ValueError("encryption_scheme not supported: %d" %
                             encryption_scheme)

        return (ciphertext, encryption_scheme)


class _DecryptionOracle(_EncryptionOracle):
    """
    This object is responsible for encrypting and decrypting secrets.

    In the future, it may interface with a subprocess or a hardware security
    module.
    """

    def reencrypt(self, ciphertext, encryption_scheme,
                  new_encryption_scheme=None):
        """
        Re-encrypt the specified secret.  If no new_encryption_scheme is
        specified (recommended), a reasonable default will be used.

        If access to the decrypted secret is not needed, this API function
        should be used to re-encrypt secrets.  In the future, this will allow
        us to keep the decrypted secrets out of the application's memory.

        Returns (ciphertext, encryption_scheme)
        """
        if self._closed:
            raise ValueError("Connection to crypto oracle already closed")

        # for now, it's all in memory anyway
        return self.encrypt(
            self.decrypt(ciphertext, encryption_scheme),
            encryption_scheme=new_encryption_scheme)

    def decrypt(self, ciphertext, encryption_scheme):
        """
        Decrypt the specified secret.

        Returns the plaintext as bytes.
        """

        if self._closed:
            raise ValueError("Connection to crypto oracle already closed")

        # sanity check
        if isinstance(ciphertext, unicode):
            raise TypeError("ciphertext should be bytes, not unicode")
        if not isinstance(encryption_scheme, (int, long)):
            raise TypeError("encryption_scheme should be an integer")
        if not 0 <= encryption_scheme <= 2**31-1:
            raise ValueError("encryption_scheme out of range")

        # decrypt differently depending on the scheme
        if encryption_scheme == EncryptionScheme.NULL:
            return ciphertext

        elif encryption_scheme == EncryptionScheme.SECRETBOX_WITH_STATIC_KEY:
            return self._secret_box.decrypt(ciphertext)

        else:
            raise ValueError("encryption_scheme not supported: %d" %
                             encryption_scheme)
