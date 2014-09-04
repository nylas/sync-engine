#!/usr/bin/env python
import os

import nacl.secret
import nacl.utils
import yaml

from inbox.config import Configuration
from inbox.models.secret import Secret
from inbox.models.session import session_scope
from inbox.models.util import EncryptionScheme


def reencrypt():
    root_path = '/etc/inboxapp'
    secrets_path = os.path.join(root_path, 'secrets.yml')
    with open(secrets_path, 'r') as f:
        cfg = Configuration(yaml.safe_load(f))

    key = cfg.get_required('SECRET_ENCRYPTION_KEY')

    with session_scope(ignore_soft_deletes=False, versioned=False) as \
            db_session:
        secrets = db_session.query(Secret).order_by(Secret.id).all()

        for s in secrets:
            if not s.encryption_scheme == \
                    EncryptionScheme.SECRETBOX_WITH_STATIC_KEY:
                continue

            if isinstance(s._secret, unicode):
                continue
            else:
                encrypted = s._secret

            try:
                decrypted = nacl.secret.SecretBox(
                    key=key,
                    encoder=nacl.encoding.HexEncoder
                ).decrypt(
                    encrypted,
                    encoder=nacl.encoding.HexEncoder)
            except TypeError:
                decrypted = nacl.secret.SecretBox(
                    key=key,
                    encoder=nacl.encoding.HexEncoder
                ).decrypt(encrypted)

            s.secret = decrypted

            db_session.add(s)

        db_session.commit()


if __name__ == '__main__':
    reencrypt()
