import json

from inbox.mailsync.backends.imap.common import update_message_metadata

from tests.util.base import add_fake_imapuid, default_account
from tests.api.base import api_client

__all__ = ['default_account', 'api_client']


def add_trash_folder(db_session, account):
    from inbox.models.folder import Folder
    return Folder.find_or_create(db_session, account, 'Trash', 'trash')


def add_spam_folder(db_session, account):
    from inbox.models.folder import Folder
    return Folder.find_or_create(db_session, account, 'Spam', 'spam')


def test_all_semantics(db, api_client, default_account, message, folder):
    trash_folder = add_trash_folder(db.session, default_account)
    add_fake_imapuid(db.session, default_account.id, message, trash_folder, 55)
    update_message_metadata(db.session, default_account, message, False)
    db.session.commit()
    resp_data = api_client.get_data('/messages/{}'.format(message.public_id))
    assert resp_data['labels'] and len(resp_data['labels']) == 1
    assert 'trash' in [l['name'] for l in resp_data['labels']]

    # Adding the 'all' label through the API ALWAYS removes the
    # 'trash'/ 'spam' labels, irrespective of whether they are included
    # in the request or not.
    trash_folder = add_trash_folder(db.session, default_account)
    db.session.commit()
    response = api_client.put_data(
        '/messages/{}'.format(message.public_id),
        {'label_ids': [folder.category.public_id,
                       trash_folder.category.public_id]})
    resp_data = json.loads(response.data)
    assert resp_data['labels'] and len(resp_data['labels']) == 1
    assert 'all' in [l['name'] for l in resp_data['labels']]


def test_trash_semantics(db, api_client, default_account, message, folder):
    # The API returns 'all' and 'inbox' labels for a Gmail message in the
    # Inbox.
    all_imapuid = add_fake_imapuid(db.session, default_account.id, message,
                                   folder, 22)
    all_imapuid.update_labels(['\\Inbox'])
    update_message_metadata(db.session, default_account, message, False)
    db.session.commit()
    resp_data = api_client.get_data('/messages/{}'.format(message.public_id))
    assert resp_data['labels'] and len(resp_data['labels']) == 2
    assert 'all' in [l['name'] for l in resp_data['labels']]
    assert 'inbox' in [l['name'] for l in resp_data['labels']]

    # Adding the 'trash' label through the API ALWAYS removes the 'all' and
    # 'inbox' labels, irrespective of whether they are included in the request
    # or not.
    trash_folder = add_trash_folder(db.session, default_account)
    db.session.commit()
    response = api_client.put_data(
        '/messages/{}'.format(message.public_id),
        {'label_ids': [folder.category.public_id,
                       trash_folder.category.public_id]})
    resp_data = json.loads(response.data)
    assert resp_data['labels'] and len(resp_data['labels']) == 1
    assert 'trash' in [l['name'] for l in resp_data['labels']]


def test_spam_semantics(db, api_client, default_account, message, folder):
    # The API returns 'all' and 'inbox' labels for a Gmail message in the
    # Inbox.
    all_imapuid = add_fake_imapuid(db.session, default_account.id, message,
                                   folder, 22)
    all_imapuid.update_labels(['\\Inbox'])
    update_message_metadata(db.session, default_account, message, False)
    db.session.commit()
    resp_data = api_client.get_data('/messages/{}'.format(message.public_id))
    assert resp_data['labels'] and len(resp_data['labels']) == 2
    assert 'all' in [l['name'] for l in resp_data['labels']]
    assert 'inbox' in [l['name'] for l in resp_data['labels']]
    inbox_label = [l['id'] for l in resp_data['labels']
                   if l['name'] == 'inbox'][0]

    # Adding the 'spam' label through the API ALWAYS removes the 'all' and
    # 'inbox' labels, irrespective of whether they are included in the request
    # or not.
    spam_folder = add_spam_folder(db.session, default_account)
    db.session.commit()
    response = api_client.put_data(
        '/messages/{}'.format(message.public_id),
        {'label_ids': [inbox_label,
                       spam_folder.category.public_id]})
    resp_data = json.loads(response.data)
    assert resp_data['labels'] and len(resp_data['labels']) == 1
    assert 'spam' in [l['name'] for l in resp_data['labels']]


def test_custom_label_semantics(db, api_client, default_account, message, folder):
    all_imapuid = add_fake_imapuid(db.session, default_account.id, message,
                                   folder, 22)
    all_imapuid.update_labels(['MyCustomLabel'])
    update_message_metadata(db.session, default_account, message, False)
    db.session.commit()
    resp_data = api_client.get_data('/messages/{}'.format(message.public_id))
    assert resp_data['labels'] and len(resp_data['labels']) == 2
    assert 'all' in [l['name'] for l in resp_data['labels']]
    assert 'MyCustomLabel' in [l['display_name'] for l in resp_data['labels']]
    custom_label = [l['id'] for l in resp_data['labels']
                    if not l['name']][0]

    # Adding the 'trash'/ 'spam' label through the API causes
    # preserves the custom label IFF included and ONLY removes it if not.
    trash_folder = add_trash_folder(db.session, default_account)
    db.session.commit()
    response = api_client.put_data(
        '/messages/{}'.format(message.public_id),
        {'label_ids': [custom_label,
                       trash_folder.category.public_id]})
    resp_data = json.loads(response.data)
    assert resp_data['labels'] and len(resp_data['labels']) == 2
    assert 'trash' in [l['name'] for l in resp_data['labels']]
    assert 'MyCustomLabel' in [l['display_name'] for l in resp_data['labels']]

    response = api_client.put_data(
        '/messages/{}'.format(message.public_id),
        {'label_ids': [trash_folder.category.public_id]})
    resp_data = json.loads(response.data)
    assert resp_data['labels'] and len(resp_data['labels']) == 1
    assert 'trash' in [l['name'] for l in resp_data['labels']]
