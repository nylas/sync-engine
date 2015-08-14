# -*- coding: utf-8 -*-
import datetime
from pytest import fixture
from inbox.models import Folder
from inbox.models.backends.imap import ImapUid
from inbox.search.base import get_search_client
from tests.util.base import (add_fake_message, add_fake_thread,
                             add_fake_imapuid, add_fake_folder)
from tests.api_legacy.base import api_client, new_api_client

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


@fixture
def patch_connection(db, generic_account, default_account):
    class MockConnection(object):
        def __init__(self):
            self.db = db
            self.generic_account_id = generic_account.id
            self.default_account_id = default_account.id

        def gmail_search(self, *args, **kwargs):
            # Get all ImapUids for gmail account
            imap_uids = db.session.query(ImapUid). \
                filter(ImapUid.account_id == self.default_account_id).all()

            return [imap_uid.msg_uid for imap_uid in imap_uids]

        def search(self, *args, **kwargs):
            # Get all ImapUids for imap account
            imap_uids = db.session.query(ImapUid). \
                filter(ImapUid.account_id == self.default_account_id).all()
            criteria = kwargs['criteria']
            assert criteria == 'TEXT blah blah blah'
            return [imap_uid.msg_uid for imap_uid in imap_uids]

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


def test_gmail_message_search(api_client, default_account,
                              patch_crispin_client,
                              patch_handler_from_provider,
                              sorted_gmail_messages):
    search_client = get_search_client(default_account)
    assert search_client.__class__.__name__ == 'GmailSearchClient'

    messages = api_client.get_data('/messages/search?q=blah%20blah%20blah')

    for sorted_message, result_message in zip(sorted_gmail_messages, messages):
        assert sorted_message.public_id == result_message['id']


def test_gmail_thread_search(api_client, test_gmail_thread, default_account,
                             patch_crispin_client,
                             patch_handler_from_provider,
                             sorted_gmail_threads):
    search_client = get_search_client(default_account)
    assert search_client.__class__.__name__ == 'GmailSearchClient'

    threads = api_client.get_data('/threads/search?q=blah%20blah%20blah')

    for sorted_thread, result_thread in zip(sorted_gmail_threads, threads):
        assert sorted_thread.public_id == result_thread['id']


def test_imap_message_search(imap_api_client, generic_account,
                              patch_crispin_client,
                              patch_handler_from_provider,
                              sorted_imap_messages):
    search_client = get_search_client(generic_account)
    assert search_client.__class__.__name__ == 'IMAPSearchClient'

    messages = imap_api_client.get_data('/messages/search?'
                                        'q=blah%20blah%20blah')

    for sorted_message, result_message in zip(sorted_imap_messages, messages):
        assert sorted_message.public_id == result_message['id']


def test_imap_thread_search(imap_api_client, generic_account,
                             patch_crispin_client,
                             patch_handler_from_provider,
                             sorted_imap_threads):
    search_client = get_search_client(generic_account)
    assert search_client.__class__.__name__ == 'IMAPSearchClient'

    threads = imap_api_client.get_data('/threads/search?q=blah%20blah%20blah')

    for sorted_thread, result_thread in zip(sorted_imap_threads, threads):
        assert sorted_thread.public_id == result_thread['id']


def test_imap_search_unicode(db, imap_api_client, generic_account,
                             patch_crispin_client,
                             patch_handler_from_provider,
                             sorted_imap_threads):
    Folder.find_or_create(db.session, generic_account,
                          '存档', '存档')
    search_client = get_search_client(generic_account)
    assert search_client.__class__.__name__ == 'IMAPSearchClient'

    threads = imap_api_client.get_data('/threads/search?q=存档')

    for sorted_thread, result_thread in zip(sorted_imap_threads, threads):
        assert sorted_thread.public_id == result_thread['id']


def test_gmail_search_unicode(db, api_client, test_gmail_thread,
                              default_account,
                              patch_crispin_client,
                              patch_handler_from_provider,
                              sorted_gmail_threads):
    Folder.find_or_create(db.session, default_account,
                          '存档', '存档')
    search_client = get_search_client(default_account)
    assert search_client.__class__.__name__ == 'GmailSearchClient'

    threads = api_client.get_data('/threads/search?q=存档')

    for sorted_thread, result_thread in zip(sorted_gmail_threads, threads):
        assert sorted_thread.public_id == result_thread['id']
