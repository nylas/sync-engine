import json
from datetime import datetime

import pytest

from tests.util.base import api_client, default_account
from tests.util.crispin import crispin_client


@pytest.fixture
def example_draft(db):
    from inbox.models import Account
    account = db.session.query(Account).get(1)
    return {
        'subject': 'Draft test at {}'.format(datetime.utcnow()),
        'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>',
        'to': [{'name': 'The red-haired mermaid',
                'email': account.email_address}]
    }


def test_send_draft(db, api_client, example_draft, default_account):
    """ Tests the save_draft function, which saves the draft to the remote. """
    from inbox.actions import _send

    r = api_client.post_data('/drafts', example_draft)
    assert r.status_code == 200

    public_id = json.loads(r.data)['id']

    r = api_client.get_data('/drafts')
    matching_saved_drafts = [draft for draft in r if draft['id'] == public_id]
    assert len(matching_saved_drafts) == 1
    draft = matching_saved_drafts[0]

    assert draft['state'] == 'draft'

    sent = _send(default_account.id, draft.id, db.session)
    assert not sent.is_draft and sent.state == 'sent'

    with crispin_client(default_account.id, default_account.provider) as c:
        criteria = ['NOT DELETED', 'SUBJECT "{0}"'.format(
            example_draft['subject'])]

        c.conn.select_folder(default_account.drafts_folder.name,
                             readonly=False)

        draft_uids = c.conn.search(criteria)
        assert not draft_uids, 'Message still in Drafts folder'

        c.conn.select_folder(default_account.sent_folder.name, readonly=False)

        sent_uids = c.conn.search(criteria)
        assert sent_uids, 'Message missing from Sent folder'

        c.conn.delete_messages(sent_uids)
        c.conn.expunge()
