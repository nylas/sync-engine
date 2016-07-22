# -*- coding: utf-8 -*-
# flake8: noqa: F401, F811
import datetime
import json
import mock
import requests
import pytest
from pytest import fixture
from inbox.models import Folder
from inbox.search.base import get_search_client
from inbox.search.backends.gmail import GmailSearchClient
from inbox.search.backends.imap import IMAPSearchClient
from tests.util.base import (add_fake_message, add_fake_thread,
                             add_fake_imapuid, add_fake_folder)
from tests.api.base import api_client, imap_api_client

__all__ = ['api_client']


@fixture
def test_gmail_thread(db, default_account):
    return add_fake_thread(db.session, default_account.namespace.id)


@fixture
def imap_folder(db, generic_account):
    f = Folder.find_or_create(db.session, generic_account,
                              'Boîte de réception', 'inbox')
    db.session.add(f)
    db.session.commit()
    return f


@fixture
def different_imap_folder(db, generic_account):
    f = Folder.find_or_create(db.session, generic_account,
                              'Archive', 'archive')
    db.session.add(f)
    db.session.commit()
    return f


@fixture
def sorted_gmail_threads(db, default_account):
    thread1 = add_fake_thread(db.session, default_account.namespace.id)
    thread2 = add_fake_thread(db.session, default_account.namespace.id)
    thread3 = add_fake_thread(db.session, default_account.namespace.id)

    return [thread1, thread2, thread3]


@fixture
def sorted_gmail_messages(db, default_account, sorted_gmail_threads, folder):
    thread1, thread2, thread3 = sorted_gmail_threads
    message1 = add_fake_message(db.session, default_account.namespace.id,
                                thread=thread1,
                                g_msgid=1,
                                from_addr=[{'name': 'Ben Bitdiddle',
                                            'email': 'ben@bitdiddle.com'}],
                                to_addr=[{'name': 'Barrack Obama',
                                          'email': 'barrack@obama.com'}],
                                received_date=datetime.
                                datetime(2015, 7, 9, 23, 50, 7),
                                subject='YOO!')

    add_fake_imapuid(db.session, default_account.id, message1,
                     folder, 3000)

    message2 = add_fake_message(db.session, default_account.namespace.id,
                                thread=thread2,
                                g_msgid=2,
                                from_addr=[{'name': 'Ben Bitdiddle',
                                            'email': 'ben@bitdiddle.com'}],
                                to_addr=[{'name': 'Barrack Obama',
                                          'email': 'barrack@obama.com'}],
                                received_date=datetime.
                                datetime(2014, 7, 9, 23, 50, 7),
                                subject='Hey!')

    add_fake_imapuid(db.session, default_account.id, message2,
                     folder, 3001)

    message3 = add_fake_message(db.session, default_account.namespace.id,
                                thread=thread3,
                                g_msgid=3,
                                from_addr=[{'name': 'Ben Bitdiddle',
                                            'email': 'ben@bitdiddle.com'}],
                                to_addr=[{'name': 'Barrack Obama',
                                          'email': 'barrack@obama.com'}],
                                received_date=datetime.
                                datetime(2013, 7, 9, 23, 50, 7),
                                subject='Sup?')

    add_fake_imapuid(db.session, default_account.id, message3,
                     folder, 3002)

    return [message1, message2, message3]


@fixture
def sorted_imap_threads(db, generic_account):
    thread1 = add_fake_thread(db.session, generic_account.namespace.id)
    thread2 = add_fake_thread(db.session, generic_account.namespace.id)
    thread3 = add_fake_thread(db.session, generic_account.namespace.id)

    return [thread1, thread2, thread3]


@fixture
def sorted_imap_messages(db, generic_account, sorted_imap_threads, imap_folder):
    thread1, thread2, thread3 = sorted_imap_threads
    message1 = add_fake_message(db.session, generic_account.namespace.id,
                                thread=thread1,
                                from_addr=[{'name': '',
                                            'email':
                                            'inboxapptest@example.com'}],
                                to_addr=[{'name': 'Ben Bitdiddle',
                                          'email': 'ben@bitdiddle.com'}],
                                received_date=datetime.
                                datetime(2015, 7, 9, 23, 50, 7),
                                subject='YOO!')

    add_fake_imapuid(db.session, generic_account.id, message1,
                     imap_folder, 2000)

    message2 = add_fake_message(db.session, generic_account.namespace.id,
                                thread=thread2,
                                from_addr=[{'name': '',
                                            'email':
                                            'inboxapptest@example.com'}],
                                to_addr=[{'name': 'Ben Bitdiddle',
                                          'email': 'ben@bitdiddle.com'}],
                                received_date=datetime.
                                datetime(2014, 7, 9, 23, 50, 7),
                                subject='Hey!')

    add_fake_imapuid(db.session, generic_account.id, message2,
                     imap_folder, 2001)

    message3 = add_fake_message(db.session, generic_account.namespace.id,
                                thread=thread3,
                                from_addr=[{'name': '',
                                            'email':
                                            'inboxapptest@example.com'}],
                                to_addr=[{'name': 'Ben Bitdiddle',
                                          'email': 'ben@bitdiddle.com'}],
                                received_date=datetime.
                                datetime(2013, 7, 9, 23, 50, 7),
                                subject='Sup?')

    add_fake_imapuid(db.session, generic_account.id, message3,
                     imap_folder, 2002)

    return [message1, message2, message3]


@fixture
def different_sorted_imap_threads(db, generic_account):
    thread1 = add_fake_thread(db.session, generic_account.namespace.id)
    thread2 = add_fake_thread(db.session, generic_account.namespace.id)
    thread3 = add_fake_thread(db.session, generic_account.namespace.id)

    return [thread1, thread2, thread3]


@fixture
def different_imap_messages(db, generic_account, different_sorted_imap_threads,
                            different_imap_folder):
    thread1, thread2, thread3 = different_sorted_imap_threads
    message1 = add_fake_message(db.session, generic_account.namespace.id,
                                thread=thread1,
                                from_addr=[{'name': '',
                                            'email':
                                            'inboxapptest@example.com'}],
                                to_addr=[{'name': 'Ben Bitdiddle',
                                          'email': 'ben@bitdiddle.com'}],
                                received_date=datetime.
                                datetime(2015, 7, 9, 23, 50, 7),
                                subject='LOL')

    add_fake_imapuid(db.session, generic_account.id, message1,
                     different_imap_folder, 5000)

    message2 = add_fake_message(db.session, generic_account.namespace.id,
                                thread=thread2,
                                from_addr=[{'name': '',
                                            'email':
                                            'inboxapptest@example.com'}],
                                to_addr=[{'name': 'Ben Bitdiddle',
                                          'email': 'ben@bitdiddle.com'}],
                                received_date=datetime.
                                datetime(2014, 7, 9, 23, 50, 7),
                                subject='ROTFLMO')

    add_fake_imapuid(db.session, generic_account.id, message2,
                     different_imap_folder, 5001)

    message3 = add_fake_message(db.session, generic_account.namespace.id,
                                thread=thread3,
                                from_addr=[{'name': '',
                                            'email':
                                            'inboxapptest@example.com'}],
                                to_addr=[{'name': 'Ben Bitdiddle',
                                          'email': 'ben@bitdiddle.com'}],
                                received_date=datetime.
                                datetime(2013, 7, 9, 23, 50, 7),
                                subject='ROFLCOPTER')

    add_fake_imapuid(db.session, generic_account.id, message3,
                     different_imap_folder, 5002)

    return [message1, message2, message3]


class MockImapConnection(object):
    def __init__(self):
        self.search_args = None

    def select_folder(self, name, **_):
        return {'UIDVALIDITY': 123}

    def logout(self):
        pass

    def search(self, criteria, charset=None):
        self.search_args = (criteria, charset)
        return [2000, 2001, 2002]

    def assert_search(self, criteria, charset=None):
        assert self.search_args == (criteria, charset)


@fixture
def imap_connection(monkeypatch):
    conn = MockImapConnection()
    monkeypatch.setattr(
        'inbox.auth.generic.GenericAuthHandler.connect_account',
        lambda *_, **__: conn)
    return conn


@fixture
def invalid_imap_connection(monkeypatch):
    from inbox.basicauth import ValidationError

    def raise_401(*args):
        raise ValidationError()
    conn = MockImapConnection()
    monkeypatch.setattr(
        'inbox.auth.generic.GenericAuthHandler.connect_account',
        raise_401)
    return conn


@fixture
def patch_token_manager(monkeypatch):
    monkeypatch.setattr(
        'inbox.models.backends.gmail.g_token_manager.get_token_for_email',
        lambda *args, **kwargs: 'token')


@fixture
def patch_gmail_search_response():
    resp = requests.Response()
    resp.status_code = 200
    resp.elapsed = datetime.timedelta(seconds=22)
    resp._content = json.dumps({
        'messages': [{'id': '1'}, {'id': '2'}, {'id': '3'}]
    })
    requests.get = mock.Mock(return_value=resp)


@fixture
def invalid_gmail_token(monkeypatch):
    from inbox.basicauth import OAuthError

    def raise_401(*args):
        raise OAuthError()
    monkeypatch.setattr(
        'inbox.models.backends.gmail.g_token_manager.get_token_for_email',
        raise_401)


@pytest.mark.parametrize('is_streaming', [True, False])
def test_gmail_message_search(api_client, default_account,
                              patch_token_manager,
                              patch_gmail_search_response,
                              sorted_gmail_messages, is_streaming):
    search_client = get_search_client(default_account)
    assert isinstance(search_client, GmailSearchClient)

    if is_streaming:
        messages = api_client.get_data('/messages/search/streaming?q=blah%20blah%20blah')
    else:
        messages = api_client.get_data('/messages/search?q=blah%20blah%20blah')

    assert_search_result(sorted_gmail_messages, messages)


@pytest.mark.parametrize('is_streaming', [True, False])
def test_gmail_thread_search(api_client, test_gmail_thread,
                             default_account,
                             patch_token_manager,
                             patch_gmail_search_response,
                             sorted_gmail_messages,
                             sorted_gmail_threads, is_streaming):
    search_client = get_search_client(default_account)
    assert isinstance(search_client, GmailSearchClient)

    if is_streaming:
        threads = api_client.get_data('/threads/search/streaming?q=blah%20blah%20blah')
    else:
        threads = api_client.get_data('/threads/search?q=blah%20blah%20blah')

    assert_search_result(sorted_gmail_threads, threads)


@pytest.mark.parametrize('is_streaming', [True, False])
def test_gmail_search_unicode(db, api_client, test_gmail_thread,
                              patch_token_manager,
                              patch_gmail_search_response,
                              default_account,
                              sorted_gmail_messages,
                              sorted_gmail_threads, is_streaming):
    search_client = get_search_client(default_account)
    assert isinstance(search_client, GmailSearchClient)

    if is_streaming:
        threads = api_client.get_data('/threads/search/streaming?q=存档')
    else:
        threads = api_client.get_data('/threads/search?q=存档')

    assert_search_result(sorted_gmail_threads, threads)


@pytest.mark.parametrize('is_streaming', [True, False])
def test_invalid_gmail_account_search(db, api_client, default_account,
                                      invalid_gmail_token,
                                      patch_gmail_search_response,
                                      sorted_gmail_messages, is_streaming):

    if is_streaming:
        response = api_client.get_raw('/messages/search/streaming?'
                                      'q=blah%20blah%20blah')
    else:
        response = api_client.get_raw('/messages/search?'
                                      'q=blah%20blah%20blah')

    assert response.status_code == 403
    assert "This search can\'t be performed because the account\'s "\
        "credentials are out of date." in json.loads(response.data)['message']


@pytest.mark.parametrize('is_streaming', [True, False])
def test_imap_message_search(imap_api_client, generic_account,
                             imap_folder, imap_connection,
                             sorted_imap_messages, is_streaming):
    search_client = get_search_client(generic_account)
    assert isinstance(search_client, IMAPSearchClient)

    if is_streaming:
        messages = imap_api_client.get_data('/messages/search/streaming?'
                                            'q=blah%20blah%20blah')
    else:
        messages = imap_api_client.get_data('/messages/search?'
                                            'q=blah%20blah%20blah')

    imap_connection.assert_search(["TEXT", "blah blah blah"])
    assert_search_result(sorted_imap_messages, messages)


@pytest.mark.parametrize('is_streaming', [True, False])
def test_imap_thread_search(imap_api_client, generic_account,
                            imap_folder, imap_connection,
                            sorted_imap_messages,
                            sorted_imap_threads, is_streaming):
    search_client = get_search_client(generic_account)
    assert isinstance(search_client, IMAPSearchClient)

    if is_streaming:
        threads = imap_api_client.get_data('/threads/search/streaming?q=blah%20blah%20blah')
    else:
        threads = imap_api_client.get_data('/threads/search?q=blah%20blah%20blah')

    imap_connection.assert_search(["TEXT", "blah blah blah"])
    assert_search_result(sorted_imap_threads, threads)


@pytest.mark.parametrize('is_streaming', [True, False])
def test_imap_thread_search_unicode(db, imap_api_client, generic_account,
                                    imap_folder, imap_connection,
                                    sorted_imap_messages,
                                    sorted_imap_threads, is_streaming):
    search_client = get_search_client(generic_account)
    assert isinstance(search_client, IMAPSearchClient)

    if is_streaming:
        threads = imap_api_client.get_data('/threads/search/streaming?q=存档')
    else:
        threads = imap_api_client.get_data('/threads/search?q=存档')

    imap_connection.assert_search([u"TEXT", u"\u5b58\u6863"], "UTF-8")
    assert_search_result(sorted_imap_threads, threads)


@pytest.mark.parametrize('is_streaming', [True, False])
def test_invalid_imap_account_search(db, imap_api_client, generic_account,
                                     invalid_imap_connection,
                                     imap_folder,
                                     sorted_imap_messages, is_streaming):

    if is_streaming:
        # Because of the way streaming search work, it will return a
        # 200 response even though we can't access the account.
        response = imap_api_client.get_raw('/messages/search/streaming?'
                                           'q=blah%20blah%20blah')
        assert response.status_code == 200
    else:
        response = imap_api_client.get_raw('/messages/search?'
                                           'q=blah%20blah%20blah')

        assert response.status_code == 403
        assert "This search can\'t be performed because the account\'s "\
            "credentials are out of date." in json.loads(response.data)['message']


def assert_search_result(expected, actual):
    assert len(expected) == len(actual)
    for expected_item, actual_item in zip(expected, actual):
        assert expected_item.public_id == actual_item['id']


@pytest.mark.parametrize('endpoint', ['messages', 'threads'])
def test_streaming_search_results(db, imap_api_client, generic_account,
                                  imap_folder, monkeypatch, sorted_imap_messages,
                                  different_imap_messages, endpoint):
    # Check that the streaming search returns results from different
    # folders.

    class MultiFolderMockImapConnection(MockImapConnection):
        def __init__(self):
            self._responses = list(reversed([
                [2000, 2001, 2002],
                [5000, 5001],
            ]))

        def search(self, criteria, charset=None):
            self.search_args = (criteria, charset)
            return self._responses.pop()

    conn = MultiFolderMockImapConnection()
    monkeypatch.setattr(
        'inbox.auth.generic.GenericAuthHandler.connect_account',
        lambda *_, **__: conn)

    search_client = get_search_client(generic_account)
    assert isinstance(search_client, IMAPSearchClient)

    url = '/{}/search/streaming?q=fantastic'.format(endpoint)
    raw_data = imap_api_client.get_raw(url).data
    assert len(conn._responses) == 0, "Search should go through both folders"

    # The API returns JSON lists separated by '\n'
    responses = raw_data.split('\n')
    assert len(responses) == 3 and responses[2] == ''
    assert len(json.loads(responses[0])) == 3
    assert len(json.loads(responses[1])) == 2
