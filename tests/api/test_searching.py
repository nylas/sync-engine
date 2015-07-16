# -*- coding: utf-8 -*-
import datetime
from pytest import fixture
from inbox.search.base import get_search_client
from tests.util.base import (add_fake_message, add_fake_thread,
                             add_fake_imapuid, new_api_client,
                             add_fake_folder)


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
def test_gmail_message(db, test_gmail_thread, default_account):
    return add_fake_message(db.session, default_account.namespace.id,
                             thread=test_gmail_thread,
                             from_addr=[{'name': 'Foo Bar',
                                         'email': 'foo@bar.com'}],
                             to_addr=[{'name': 'Ben Bitdiddle',
                                       'email': 'ben@bitdiddle.com'}],
                             received_date=datetime.
                             datetime(2015, 7, 9, 23, 50, 7),
                             subject='YOO!')


@fixture
def test_gmail_imap_uid(db, test_gmail_message, default_account, folder):
    return add_fake_imapuid(db.session,
                            default_account.id,
                            test_gmail_message,
                            folder,
                            1337)


@fixture
def test_imap_thread(db, generic_account):
    return add_fake_thread(db.session, generic_account.namespace.id)


@fixture
def test_imap_message(db, test_imap_thread, generic_account):
    return add_fake_message(db.session, generic_account.namespace.id,
                             thread=test_imap_thread,
                             from_addr=[{'name': 'Foo Bar',
                                         'email': 'foo@bar.com'}],
                             to_addr=[{'name': 'Ben Bitdiddle',
                                       'email': 'ben@bitdiddle.com'}],
                             received_date=datetime.
                             datetime(2015, 7, 9, 23, 50, 7),
                             subject='YOO!')


@fixture
def test_imap_uid(db, test_imap_message, generic_account, imap_folder):
    return add_fake_imapuid(db.session,
                            generic_account.id,
                            test_imap_message,
                            imap_folder,
                            2222)


@fixture
def patch_connection():
    class MockConnection(object):
        def __init__(self):
            pass

        def gmail_search(self, *args, **kwargs):
            return [1337]

        def search(self, *args, **kwargs):
            criteria = kwargs['criteria']
            assert criteria == 'TEXT blah blah blah'
            return [2222]

    return MockConnection()


@fixture
def patch_oauth_handler():
    class MockOAuthAuthHandler(object):
        def __init__(self, *args, **kwargs):
            pass

        def connect_account(self, *args, **kwargs):
            return ''

        def get_token(self, *args, **kwargs):
            return 'faketoken'

        def new_token(self, *args, **kwargs):
            return 'faketoken'

    return MockOAuthAuthHandler()


@fixture
def patch_handler_from_provider(monkeypatch, patch_oauth_handler):
    def mock_handler_from_provider(provider_name):
        return patch_oauth_handler

    monkeypatch.setattr('inbox.auth.base.handler_from_provider',
                        mock_handler_from_provider)


@fixture
def patch_crispin_client(monkeypatch, patch_connection):
    class MockCrispinClient(object):
        def __init__(self, *args, **kwargs):
            self.conn = patch_connection

        def select_folder(self, *args, **kwargs):
            pass

        def logout(self):
            pass

    monkeypatch.setattr('inbox.crispin.CrispinClient',
                        MockCrispinClient)
    monkeypatch.setattr('inbox.crispin.GmailCrispinClient',
                        MockCrispinClient)


def test_gmail_message_search(api_client, test_gmail_message, default_account,
                              patch_crispin_client,
                              patch_handler_from_provider,
                              test_gmail_imap_uid):
    search_client = get_search_client(default_account)
    assert search_client.__class__.__name__ == 'GmailSearchClient'

    messages = api_client.get_data('/messages/search?q=blah%20blah%20blah')

    assert len(messages) == 1
    assert messages[0]['id'] == test_gmail_message.public_id


def test_gmail_thread_search(api_client, test_gmail_thread, default_account,
                             patch_crispin_client,
                             patch_handler_from_provider,
                             test_gmail_imap_uid):
    search_client = get_search_client(default_account)
    assert search_client.__class__.__name__ == 'GmailSearchClient'

    threads = api_client.get_data('/threads/search?q=blah%20blah%20blah')

    assert len(threads) == 1
    assert threads[0]['id'] == test_gmail_thread.public_id


def test_imap_message_search(imap_api_client, test_imap_message,
                              generic_account,
                              patch_crispin_client,
                              patch_handler_from_provider,
                              test_imap_uid):
    search_client = get_search_client(generic_account)
    assert search_client.__class__.__name__ == 'IMAPSearchClient'

    messages = imap_api_client.get_data('/messages/search?'
                                        'q=blah%20blah%20blah')

    assert len(messages) == 1
    assert messages[0]['id'] == test_imap_message.public_id


def test_imap_thread_search(imap_api_client, test_imap_thread, generic_account,
                             patch_crispin_client,
                             patch_handler_from_provider,
                             test_imap_uid):
    search_client = get_search_client(generic_account)
    assert search_client.__class__.__name__ == 'IMAPSearchClient'

    threads = imap_api_client.get_data('/threads/search?q=blah%20blah%20blah')

    assert len(threads) == 1
    assert threads[0]['id'] == test_imap_thread.public_id
