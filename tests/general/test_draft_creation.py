from inbox.sendmail.base import create_message_from_json, update_draft


def test_headers_presence(default_namespace, db):
    data = {'subject': 'test draft', 'to': [{'email': 'karim@nylas.com'}]}
    draft = create_message_from_json(data, default_namespace, db.session,
                                     False)

    assert draft.inbox_uid is not None
    assert draft.message_id_header is not None

    old_uid = draft.inbox_uid

    update_draft(db.session, default_namespace.account, draft,
                 body="updated body", blocks=[])

    assert draft.inbox_uid is not None
    assert draft.message_id_header is not None
    assert draft.inbox_uid != old_uid
