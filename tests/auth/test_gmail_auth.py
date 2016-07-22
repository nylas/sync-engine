import copy
import mock

import pytest

from inbox.models.account import Account
from inbox.auth.gmail import GmailAuthHandler
from inbox.basicauth import ImapSupportDisabledError

settings = {'email': 't.est@gmail.com',
            'name': 'T.Est',
            'refresh_token': 'MyRefreshToken',
            'scope': '',
            'id_token': '',
            'sync_email': True,
            'contacts': False,
            'events': True}


@pytest.fixture
def patched_gmail_client(monkeypatch):
    def raise_exc(*args, **kwargs):
        raise ImapSupportDisabledError()

    monkeypatch.setattr('inbox.crispin.GmailCrispinClient.__init__',
                        raise_exc)


def test_create_account(db):
    handler = GmailAuthHandler('gmail')

    # Create an account
    account = handler.create_account(settings['email'], settings)
    db.session.add(account)
    db.session.commit()
    # Verify its settings
    id_ = account.id
    account = db.session.query(Account).get(id_)
    assert account.email_address == settings['email']
    assert account.name == settings['name']
    assert account.sync_email == settings['sync_email']
    assert account.sync_contacts == settings['contacts']
    assert account.sync_events == settings['events']
    # Ensure that the emailed events calendar was created
    assert account._emailed_events_calendar is not None
    assert account._emailed_events_calendar.name == 'Emailed events'


def test_update_account(db):
    handler = GmailAuthHandler('gmail')

    # Create an account
    account = handler.create_account(settings['email'], settings)
    db.session.add(account)
    db.session.commit()
    id_ = account.id

    # Verify it is updated correctly.
    updated_settings = copy.deepcopy(settings)
    updated_settings['name'] = 'Neu!'
    account = handler.update_account(account, updated_settings)
    db.session.add(account)
    db.session.commit()
    account = db.session.query(Account).get(id_)
    assert account.name == 'Neu!'


def test_verify_account(db, patched_gmail_client):
    handler = GmailAuthHandler('gmail')
    handler.connect_account = lambda account: None

    # Create an account with sync_email=True
    account = handler.create_account(settings['email'], settings)
    db.session.add(account)
    db.session.commit()
    assert account.sync_email is True
    # Verify an exception is raised if there is an email settings error.
    with pytest.raises(ImapSupportDisabledError):
        handler.verify_account(account)

    # Create an account with sync_email=True
    updated_settings = copy.deepcopy(settings)
    updated_settings['email'] = 'another@gmail.com'
    updated_settings['sync_email'] = False
    account = handler.create_account(updated_settings['email'], updated_settings)
    db.session.add(account)
    db.session.commit()
    assert account.sync_email is False
    # Verify an exception is NOT raised if there is an email settings error.
    account = handler.verify_account(account)


def test_successful_reauth_resets_sync_state(monkeypatch, db):
    monkeypatch.setattr('inbox.auth.gmail.GmailCrispinClient', mock.Mock())
    handler = GmailAuthHandler('gmail')
    handler.connect_account = lambda account: mock.Mock()

    account = handler.create_account(settings['email'], settings)
    assert handler.verify_account(account) is True
    # Brand new accounts have `sync_state`=None.
    assert account.sync_state is None
    db.session.add(account)
    db.session.commit()

    # Pretend account sync starts, and subsequently the password changes,
    # causing the account to be in `sync_state`='invalid'.
    account.mark_invalid()
    db.session.commit()
    assert account.sync_state == 'invalid'

    # Verify the `sync_state` is reset to 'running' on a successful "re-auth".
    account = handler.update_account(account, settings)
    assert handler.verify_account(account) is True
    assert account.sync_state == 'running'
    db.session.add(account)
    db.session.commit()
