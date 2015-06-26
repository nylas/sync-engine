from inbox.sendmail.base import create_draft, update_draft
from tests.util.base import default_namespace, db


def test_headers_presence(default_namespace, db):
    data = {'subject': 'test draft', 'to': [{'email': 'karim@nylas.com'}]}
    draft = create_draft(data, default_namespace, db.session, False)

    assert draft.inbox_uid is not None
    assert draft.message_id_header is not None

    old_uid = draft.inbox_uid

    update_draft(db.session, default_namespace.account, draft,
                 body="updated body", blocks=[])

    assert draft.inbox_uid is not None
    assert draft.message_id_header is not None
    assert draft.inbox_uid != old_uid
