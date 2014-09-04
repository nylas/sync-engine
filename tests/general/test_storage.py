from datetime import datetime

from inbox.models import Account, Message
from inbox.models.util import EncryptionScheme
from ..data.messages.replyto_message import message

ACCOUNT_ID = 1
THREAD_ID = 1


def test_local_storage(db, config):
    account = db.session.query(Account).get(ACCOUNT_ID)
    m = Message(account=account, mid='', folder_name='',
                received_date=datetime.utcnow(),
                flags='', body_string=message)
    m.thread_id = THREAD_ID

    db.session.add(m)
    db.session.commit()

    msg = db.session.query(Message).get(m.id)

    # Ensure .data will access and decrypt the encrypted data from disk
    assert not hasattr(msg, '_data')

    for b in [p.block for p in msg.parts]:
        assert b.encryption_scheme == \
            EncryptionScheme.SECRETBOX_WITH_STATIC_KEY

        # Accessing .data verifies data integrity
        data = b.data

        raw = b._get_from_disk
        assert data != raw


def test_s3_storage():
    # TODO[k]
    pass
