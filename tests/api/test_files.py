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
    assert len(results) == 1

    results = api_client.get_data('/files?content_type=audio%2Fx-wav')
    assert len(results) == 1

    results = api_client.get_data('/files?content_type=image%2Fjpeg')
    assert len(results) == 2


def test_attachment_has_same_id(api_client, uploaded_file_ids, draft):
    attachment_id = uploaded_file_ids.pop()
    draft['file_ids'] = [attachment_id]
    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 200
    draft_resp = json.loads(r.data)
    assert attachment_id in [x['id'] for x in draft_resp['files']]


def test_delete(api_client, uploaded_file_ids, draft):
    non_attachment_id = uploaded_file_ids.pop()
    attachment_id = uploaded_file_ids.pop()
    draft['file_ids'] = [attachment_id]
    r = api_client.post_data('/drafts', draft)
    assert r.status_code == 200

    # Test that we can delete a non-attachment
    r = api_client.delete('/files/{}'.format(non_attachment_id))
    assert r.status_code == 200

    data = api_client.get_data('/files/{}'.format(non_attachment_id))
    assert data['message'].startswith("Couldn't find file")

    # Make sure that we cannot delete attachments
    r = api_client.delete('/files/{}'.format(attachment_id))
    assert r.status_code == 400

    data = api_client.get_data('/files/{}'.format(attachment_id))
    assert data['id'] == attachment_id


@pytest.mark.parametrize("filename", FILENAMES)
def test_get_with_id(api_client, uploaded_file_ids, filename):
    in_file = api_client.get_data('/files?filename={}'.format(filename))[0]
    data = api_client.get_data('/files/{}'.format(in_file['id']))
    assert data['filename'] == filename


def test_get_invalid(api_client, uploaded_file_ids):
    data = api_client.get_data('/files/0000000000000000000000000')
    assert data['message'].startswith("Couldn't find file")
    data = api_client.get_data('/files/!')
    assert data['message'].startswith("Invalid file id")

    data = api_client.get_data('/files/0000000000000000000000000/download')
    assert data['message'].startswith("Couldn't find file")
    data = api_client.get_data('/files/!/download')
    assert data['message'].startswith("Invalid file id")

    r = api_client.delete('/files/0000000000000000000000000')
    assert r.status_code == 404
    r = api_client.delete('/files/!')
    assert r.status_code == 400


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

    assert new_orphan == old_orphan - 1
    assert new_total == old_total


@pytest.mark.parametrize("filename", FILENAMES)
def test_download(api_client, uploaded_file_ids, filename):
    import md5
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                        'data', filename)
    in_file = api_client.get_data('/files?filename={}'.format(filename))[0]
    data = api_client.get_raw('/files/{}/download'.format(in_file['id']))

    local_data = open(path, 'rb').read()
    local_md5 = md5.new(local_data).digest()
    dl_md5 = md5.new(data).digest()
    assert local_md5 == dl_md5
