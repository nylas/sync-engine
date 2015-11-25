# -*- coding: utf-8 -*-
import datetime
import json
import mock
import requests
from pytest import fixture
from inbox.models import Folder
from inbox.search.base import get_search_client
from inbox.search.backends.gmail import GmailSearchClient
from inbox.search.backends.imap import IMAPSearchClient
from tests.util.base import (add_fake_message, add_fake_thread,
                             add_fake_imapuid, add_fake_folder)
from tests.api.base import api_client, new_api_client

__all__ = ['api_client']


@fixture
def imap_api_client(db, generic_account):
    return new_api_client(db, generic_account.namespace)


@fixture
def test_gmail_thread(db, default_account):
    return add_fake_thread(db.session, default_account.namespace.id)


@fixture
def imap_folder(db, generic_account):
    return add_fake_folder(db, generic_account)


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
def sorted_imap_messages(db, generic_account, sorted_imap_threads, folder):
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
                     folder, 2000)

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
                     folder, 2001)

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
                     folder, 2002)

    return [message1, message2, message3]


class MockConnection(object):
    def search(self, *args, **kwargs):
        criteria = kwargs['criteria']
        assert criteria == 'TEXT blah blah blah'
        return [2000, 2001, 2002]

    def logout(self):
        pass


@fixture
def patch_crispin_client(monkeypatch):
    monkeypatch.setattr(
        'inbox.auth.generic.GenericAuthHandler.connect_account',
        lambda *args, **kwargs: MockConnection())


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


def test_gmail_message_search(api_client, default_account,
                              patch_token_manager,
                              patch_gmail_search_response,
                              sorted_gmail_messages):
    search_client = get_search_client(default_account)
    assert isinstance(search_client, GmailSearchClient)

    messages = api_client.get_data('/messages/search?q=blah%20blah%20blah')

    for sorted_message, result_message in zip(sorted_gmail_messages, messages):
        assert sorted_message.public_id == result_message['id']


def test_gmail_thread_search(api_client, test_gmail_thread, default_account,
                             patch_token_manager,
                             patch_gmail_search_response,
                             sorted_gmail_threads):
    search_client = get_search_client(default_account)
    assert isinstance(search_client, GmailSearchClient)

    threads = api_client.get_data('/threads/search?q=blah%20blah%20blah')

    for sorted_thread, result_thread in zip(sorted_gmail_threads, threads):
        assert sorted_thread.public_id == result_thread['id']


def test_imap_message_search(imap_api_client, generic_account,
                              patch_crispin_client,
                              sorted_imap_messages):
    search_client = get_search_client(generic_account)
    assert isinstance(search_client, IMAPSearchClient)

    messages = imap_api_client.get_data('/messages/search?'
                                        'q=blah%20blah%20blah')

    for sorted_message, result_message in zip(sorted_imap_messages, messages):
        assert sorted_message.public_id == result_message['id']


def test_imap_thread_search(imap_api_client, generic_account,
                             patch_crispin_client,
                             sorted_imap_threads):
    search_client = get_search_client(generic_account)
    assert isinstance(search_client, IMAPSearchClient)

    threads = imap_api_client.get_data('/threads/search?q=blah%20blah%20blah')

    for sorted_thread, result_thread in zip(sorted_imap_threads, threads):
        assert sorted_thread.public_id == result_thread['id']


def test_imap_search_unicode(db, imap_api_client, generic_account,
                             patch_crispin_client,
                             sorted_imap_threads):
    Folder.find_or_create(db.session, generic_account,
                          '存档', '存档')
    search_client = get_search_client(generic_account)
    assert isinstance(search_client, IMAPSearchClient)

    threads = imap_api_client.get_data('/threads/search?q=存档')

    for sorted_thread, result_thread in zip(sorted_imap_threads, threads):
        assert sorted_thread.public_id == result_thread['id']


def test_gmail_search_unicode(db, api_client, test_gmail_thread,
                              patch_token_manager,
                              patch_gmail_search_response,
                              default_account,
                              sorted_gmail_threads):
    Folder.find_or_create(db.session, default_account,
                          '存档', '存档')
    search_client = get_search_client(default_account)
    assert isinstance(search_client, GmailSearchClient)

    threads = api_client.get_data('/threads/search?q=存档')

    for sorted_thread, result_thread in zip(sorted_gmail_threads, threads):
        assert sorted_thread.public_id == result_thread['id']
