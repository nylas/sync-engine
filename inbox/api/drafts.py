from nylas.logging import get_logger
log = get_logger()
from inbox.models import Account
from inbox.actions.backends.generic import (remote_save_draft,
                                            remote_update_draft,
                                            remote_delete_draft)


def create_draft_on_remote(db_session, account_id, draft):
    account = db_session.query(Account).get(account_id)
    if account.discriminator == 'easaccount':
        log.warning('Skipping remote draft action for Exchange account',
                    action='create_draft', account_id=account_id)
        return draft
    remote_save_draft(db_session, account_id, draft)


def update_draft_on_remote(db_session, account_id, draft):
    account = db_session.query(Account).get(account_id)
    if account.discriminator == 'easaccount':
        log.warning('Skipping remote draft action for Exchange account',
                    action='update_draft', account_id=account_id)
        return draft
    remote_update_draft(db_session, account_id, draft)


def delete_draft_on_remote(db_session, account_id, draft):
    account = db_session.query(Account).get(account_id)
    if account.discriminator == 'easaccount':
        log.warning('Skipping remote draft action for Exchange account',
                    action='delete_draft', account_id=account_id)
        return
    remote_delete_draft(db_session, account_id, draft)
