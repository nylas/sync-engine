from inbox.models.account import Account
from inbox.models.event import Event
from inbox.events.actions.backends import module_registry
from inbox.events.ical import (generate_icalendar_invite, send_invite)


def create_event(account_id, event_id, db_session, extra_args):
    account = db_session.query(Account).get(account_id)
    event = db_session.query(Event).get(event_id)
    remote_create_event = module_registry[account.provider].remote_create_event

    remote_create_event(account, event, db_session, extra_args)

    notify_participants = extra_args.get('notify_participants', False)
    # Do we need to send an RSVP message?
    # We use gmail's sendNotification API for google accounts.
    # but we need create and send an iCalendar invite ourselves
    # for non-gmail accounts.
    if notify_participants and account.provider != 'gmail':
        ical_file = generate_icalendar_invite(event).to_ical()

        html_body = ''
        send_invite(ical_file, event, html_body, account)


def update_event(account_id, event_id, db_session, extra_args):
    account = db_session.query(Account).get(account_id)
    event = db_session.query(Event).get(event_id)

    remote_update_event = module_registry[account.provider].remote_update_event

    remote_update_event(account, event, db_session, extra_args)

    notify_participants = extra_args.get('notify_participants', False)

    if notify_participants and account.provider != 'gmail':
        ical_file = generate_icalendar_invite(event).to_ical()

        html_body = ''
        send_invite(ical_file, event, html_body, account)


def delete_event(account_id, event_id, db_session, extra_args):
    account = db_session.query(Account).get(account_id)
    remote_delete_event = module_registry[account.provider].remote_delete_event
    event_uid = extra_args.pop('event_uid', None)
    calendar_name = extra_args.pop('calendar_name', None)

    # The calendar_uid argument is required for some providers, like EAS.
    calendar_uid = extra_args.pop('calendar_uid', None)

    remote_delete_event(account, event_uid, calendar_name, calendar_uid,
                        db_session, extra_args)
