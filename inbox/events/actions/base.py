from inbox.models.account import Account
from inbox.models.event import Event
from inbox.models.session import session_scope
from inbox.events.actions.backends import module_registry
from inbox.events.ical import (generate_icalendar_invite, send_invite)


def create_event(account_id, event_id, extra_args):
    with session_scope(account_id) as db_session:
        account = db_session.query(Account).get(account_id)
        event = db_session.query(Event).get(event_id)
        remote_create_event = module_registry[account.provider]. \
            remote_create_event

        remote_create_event(account, event, db_session, extra_args)

        notify_participants = extra_args.get('notify_participants', False)
        cancelled_participants = extra_args.get('cancelled_participants', [])
        # Do we need to send an RSVP message?
        # We use gmail's sendNotification API for google accounts.
        # but we need create and send an iCalendar invite ourselves
        # for non-gmail accounts.
        if notify_participants and account.provider != 'gmail':
            ical_file = generate_icalendar_invite(event).to_ical()
            send_invite(ical_file, event, account, invite_type='request')

            if cancelled_participants != []:
                # Some people got removed from the event. Send them a
                # cancellation email.
                event.status = 'cancelled'
                event.participants = cancelled_participants
                ical_file = generate_icalendar_invite(event,
                                                      invite_type='cancel').to_ical()
                send_invite(ical_file, event, account, invite_type='cancel')


def update_event(account_id, event_id, extra_args):
    with session_scope(account_id) as db_session:
        account = db_session.query(Account).get(account_id)
        event = db_session.query(Event).get(event_id)

        # Update our copy of the event before sending it.
        if 'event_data' in extra_args:
            data = extra_args['event_data']
            for attr in Event.API_MODIFIABLE_FIELDS:
                if attr in extra_args['event_data']:
                    setattr(event, attr, data[attr])

            event.sequence_number += 1

        # It doesn't make sense to update or delete an event we imported from
        # an iCalendar file.
        if event.calendar == account.emailed_events_calendar:
            return

        remote_update_event = module_registry[account.provider]. \
            remote_update_event

        remote_update_event(account, event, db_session, extra_args)

        notify_participants = extra_args.get('notify_participants', False)

        if notify_participants and account.provider != 'gmail':
            ical_file = generate_icalendar_invite(event).to_ical()
            send_invite(ical_file, event, account, invite_type='update')

        db_session.commit()


def delete_event(account_id, event_id, extra_args):
    with session_scope(account_id) as db_session:
        account = db_session.query(Account).get(account_id)
        event = db_session.query(Event).get(event_id)
        notify_participants = extra_args.get('notify_participants', False)

        remote_delete_event = module_registry[account.provider]. \
            remote_delete_event
        event_uid = extra_args.pop('event_uid', None)
        calendar_name = extra_args.pop('calendar_name', None)

        # The calendar_uid argument is required for some providers, like EAS.
        calendar_uid = extra_args.pop('calendar_uid', None)

        if event.calendar == account.emailed_events_calendar:
            return

        remote_delete_event(account, event_uid, calendar_name, calendar_uid,
                            db_session, extra_args)

        # Finally, update the event.
        event.sequence_number += 1
        event.status = 'cancelled'
        db_session.commit()

        if notify_participants and account.provider != 'gmail':
            ical_file = generate_icalendar_invite(event,
                                                  invite_type='cancel').to_ical()

            send_invite(ical_file, event, account, invite_type='cancel')
