"""This is the syncback code for events.
It's inspired by the email syncback code

Note: these actions must be idempotent.
"""

# Allow out-of-tree action submodules.
from inbox.log import get_logger
from inbox.models import Account, Event
from inbox.events.actions.backends import module_registry

log = get_logger()


def create_event(account_id, event_id, db_session):
    account = db_session.query(Account).get(account_id)
    event = db_session.query(Event).get(event_id)

    remote_create = module_registry[account.provider]. \
         remote_create

    remote_create(account, event, db_session)


def update_event(account_id, event_id, db_session):
    account = db_session.query(Account).get(account_id)
    event = db_session.query(Event).get(event_id)

    remote_update = module_registry[account.provider]. \
         remote_update

    remote_update(account, event, db_session)


def delete_event(account_id, event_id, db_session):
    account = db_session.query(Account).get(account_id)
    event = db_session.query(Event).get(event_id)

    remote_delete = module_registry[account.provider]. \
         remote_delete

    remote_delete(account, event, db_session)
