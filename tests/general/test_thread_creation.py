# test that T441 doesn't reappear, ever.
import pytest
from collections import namedtuple


MockMessage = namedtuple('Message', ['subject'])
MockImapUID = namedtuple('ImapUid', ['message'])


def test_generic_foldersyncengine(db, monkeypatch):
    # super ugly, but I don't want to have to mock tons of stuff
    import inbox.mailsync.backends.imap.generic
    monkeypatch.setattr(inbox.mailsync.backends.imap.generic,
                        "_pool", lambda(account): True)

    from inbox.mailsync.backends.imap.generic import FolderSyncEngine
    from inbox.auth.generic import create_account

    # setup a dummy FolderSyncEngine - we only need to call a couple
    # methods.
    email = "inboxapptest1@fastmail.fm"
    account = create_account(db.session, email,
                             {"email": email, "password": "BLAH"})
    db.session.commit()

    engine = None
    messages = []
    engine = FolderSyncEngine(account.id, "Inbox", 0,
                              email, "fastmail",
                              3200, None, 20, None)

    message = MockMessage("Golden Gate Park next Sat")
    imapuid = MockImapUID(message)
    messages = engine.fetch_similar_threads(db.session, imapuid, None, None)
    assert messages == [], ("fetch_similar_threads should "
                            "heed namespace boundaries")

if __name__ == '__main__':
    pytest.main([__file__])
