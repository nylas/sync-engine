import os
import json
from datetime import datetime
import pytest
from tests.util.base import api_client

__all__ = ['api_client']

FILENAMES = ['muir.jpg', 'LetMeSendYouEmail.wav', 'first-attachment.jpg']


@pytest.fixture
def draft(db):
    from inbox.models import Account
    account = db.session.query(Account).get(1)
    return {
        'subject': 'Draft test at {}'.format(datetime.utcnow()),
        'body': '<html><body><h2>Sea, birds and sand.</h2></body></html>',
        'to': [{'name': 'The red-haired mermaid',
                'email': account.email_address}]
    }


@pytest.fixture(scope='function')
def files(db):
    filenames = FILENAMES
    data = []
    for filename in filenames:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                            'data', filename)
        data.append((filename, path))
    return data


@pytest.fixture(scope='function')
def uploaded_file_ids(api_client, files):
    file_ids = []
    upload_path = api_client.full_path('/files')
    for filename, path in files:
        data = {'file': (open(path, 'rb'), filename)}
        r = api_client.client.post(upload_path, data=data)
        assert r.status_code == 200
        file_id = json.loads(r.data)[0]['id']
        file_ids.append(file_id)

    return file_ids


def test_file_filtering(api_client, uploaded_file_ids, draft):
    for f_id in uploaded_file_ids:
        results = api_client.get_data('/files?file_id={}'
                                      .format(f_id))
        assert len(results) == 1

    # Attach the files to a draft and search there
    draft['file_ids'] = uploaded_file_ids
    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 200

    draft_resp = json.loads(r.data)
    assert len(draft_resp['files']) == 3
    d_id = draft_resp['id']

    results = api_client.get_data('/files?message_id={}'
                                  .format(d_id))
    assert len(results) == 3

    results = api_client.get_data('/files?message_id={}&limit=1'
                                  .format(d_id))
    assert len(results) == 1

    results = api_client.get_data('/files?message_id={}&offset=2'
                                  .format(d_id))
    assert len(results) == 1

    results = api_client.get_data('/files?filename=LetMeSendYouEmail.wav')
    # TODO: files should be de-duped on backend and result should be 1
    assert len(results) == 2

    results = api_client.get_data('/files?content_type=audio%2Fx-wav')
    # TODO: files should be de-duped on backend and result should be 1
    assert len(results) == 2

    results = api_client.get_data('/files?content_type=image%2Fjpeg')
    # TODO: files should be de-duped on backend and result should be 2
    assert len(results) == 4


def test_is_attachment_filtering(api_client, uploaded_file_ids, draft):
    """Attach files to draft, make sure we can use is_attachment specifier"""
    old_total = len(api_client.get_data('/files'))
    old_orphan = len(api_client.get_data('/files?is_attachment=0'))
    old_attach = len(api_client.get_data('/files?is_attachment=1'))
    assert old_attach + old_orphan == old_total

    draft['file_ids'] = [uploaded_file_ids.pop()]
    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 200

    draft_resp = json.loads(r.data)
    assert len(draft_resp['files']) == 1

    new_total = len(api_client.get_data('/files'))
    new_orphan = len(api_client.get_data('/files?is_attachment=0'))
    new_attach = len(api_client.get_data('/files?is_attachment=1'))
    assert new_attach + new_orphan == new_total
    assert new_attach == old_attach + 1

    # TODO: de-dup files on backend
    assert new_orphan == old_orphan
    assert new_total == old_total + 1
