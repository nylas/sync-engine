def test_delete_cascades(db):
    from inbox.server.models.tables.base import Message, Part
    from inbox.server.models.tables.imap import ImapUid

    message = db.session.query(Message).join(ImapUid, Part).filter(
            Message.id==2).one()
    uid_id = message.imapuid.id

    assert len(message.parts), \
        "this test won't work properly since this message has no parts"

    db.session.delete(message)
    db.session.commit()

    assert db.session.query(ImapUid).filter_by(id=uid_id).count(), \
        'associated ImapUid should still be present'
    assert not db.session.query(Message).filter_by(id=2).count(), \
        'Message should be deleted'
    assert not db.session.query(Part).filter_by(message_id=2).count(), \
        'associated Blocks should be deleted by cascade'

    uid = db.session.query(ImapUid).filter_by(id=1).one()
    message_id = uid.message_id

    db.session.delete(uid)
    db.session.commit()
    assert not db.session.query(Message).filter_by(id=message_id).count(), \
            'associated Message should be deleted by cascade'
