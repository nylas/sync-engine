""" Tests for automatic soft delete query filter. """

import datetime

import pytest

from sqlalchemy.orm.exc import NoResultFound

ACCOUNT_ID = 1


def test_soft_delete(db, config):
    from inbox.models.tables.base import Folder, Message
    from inbox.models.tables.imap import ImapUid
    f = Folder(name='DOES NOT EXIST', account_id=ACCOUNT_ID)
    db.session.add(f)
    db.session.flush()
    m = Message(thread_id=1, received_date=datetime.datetime.utcnow(),
                size=0, sanitized_body="", snippet="")
    u = ImapUid(message=m, imapaccount_id=ACCOUNT_ID, folder_id=f.id,
                msg_uid=9999, extra_flags="")
    db.session.add_all([m, u])
    f.mark_deleted()
    u.mark_deleted()
    db.session.commit()
    m_id = m.id

    # bypass custom query method to confirm creation
    db.new_session(ignore_soft_deletes=False)
    f = db.session.query(Folder).filter_by(name='DOES NOT EXIST').one()
    assert f, "Can't find Folder object"
    assert f.deleted_at is not None, "Folder not marked as deleted"

    db.new_session(ignore_soft_deletes=True)

    with pytest.raises(NoResultFound):
        folders = db.session.query(Folder).filter(
            Folder.name == 'DOES NOT EXIST').one()

    count = db.session.query(Folder).filter(
        Folder.name == 'DOES NOT EXIST').count()
    assert count == 0, "Shouldn't find any deleted folders!"

    m = db.session.query(Message).filter_by(id=m_id).one()
    assert not m.imapuids, "imapuid was deleted!"
