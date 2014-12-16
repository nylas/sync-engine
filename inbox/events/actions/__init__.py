"""
This is the syncback code for events.
It's inspired by the email syncback code.

Note: these actions must be idempotent.

"""
# Allow out-of-tree action submodules.
from inbox.log import get_logger
log = get_logger()
from inbox.models import Account, Event
from inbox.events.actions.backends import module_registry


def create_event(account_id, event_id, db_session):
    account = db_session.query(Account).get(account_id)
    event = db_session.query(Event).get(event_id)

    remote_create_event = module_registry[account.provider]. \
         remote_create_event

    remote_create_event(account, event, db_session)


def update_event(account_id, event_id, db_session):
    account = db_session.query(Account).get(account_id)
    event = db_session.query(Event).get(event_id)

    remote_update_event = module_registry[account.provider]. \
         remote_update_event

    remote_update_event(account, event, db_session)


def delete_event(account_id, event_id, db_session, args):
    account = db_session.query(Account).get(account_id)
    remote_delete_event = module_registry[account.provider]. \
         remote_delete_event
    event_uid = args.get('event_uid')
    calendar_name = args.get('calendar_name')

    remote_delete_event(account, event_uid, calendar_name, db_session)
