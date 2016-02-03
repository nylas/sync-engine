import pytest

from tests.util.base import add_fake_gmail_account


def add_fake_imap_account(db_session, provider, email_address, password):
    from inbox.models import Namespace
    from inbox.models.backends.generic import GenericAccount
    namespace = Namespace()
    account = GenericAccount(namespace=namespace, provider=provider,
                             email_address=email_address,
                             imap_password=password,
                             smtp_password=password)
    db_session.add(account)
    db_session.commit()
    return account


@pytest.fixture
def fake_imap_accounts(db):
    imap_account_data = {
        'yahoo': 'cypresstest@yahoo.com',
        'aol': 'benbitdit@aol.com',
        'icloud': 'inbox.watchdog@icloud.com',
        'imap': 'heyhey@mycustomimap.com',
    }
    accounts = {'gmail': add_fake_gmail_account(db.session)}
    for provider, email in imap_account_data.items():
        accounts[provider] = add_fake_imap_account(db.session, provider, email,
                                                   'sEcr3T')
    return accounts


def test_provider_setting(db, fake_imap_accounts):
    for provider, account in fake_imap_accounts.items():
        assert account.provider == provider
        assert account.verbose_provider == provider
