import pytz
from datetime import datetime
from icalendar import Calendar as iCalendar

from inbox.models.account import Account
from inbox.models.event import Event
from inbox.models.calendar import Calendar
from inbox.models.session import session_scope
from inbox.events.util import MalformedEventError


def events_from_ics(namespace, calendar, ics_str):
    try:
        cal = iCalendar.from_ical(ics_str)
    except ValueError:
        raise MalformedEventError()

    print ics_str
    events = []
    for component in cal.walk():
        if component.name == "VEVENT":
            # Make sure the times are in UTC.
            original_start = component.get('dtstart').dt.astimezone(pytz.utc)
            original_end = component.get('dtend').dt.astimezone(pytz.utc)

            # MySQL doesn't like localized datetimes.
            start = original_start.replace(tzinfo=None)
            end = original_end.replace(tzinfo=None)

            title = component.get('summary')
            description = unicode(component.get('description'))

            if isinstance(start, datetime):
                all_day = False
            else:
                all_day = True
                start = datetime.combine(start, datetime.min.time())
                end = datetime.combine(end, datetime.min.time())

            reccur = component.get('rrule')
            if reccur:
                reccur = reccur.to_ical()
            else:
                reccur = ''
            participants = []
            attendees = component.get('attendee')

            # the iCalendar python module doesn't return a list when
            # there's only one attendee. Go figure.
            if not isinstance(attendees, list):
                attendees = [attendees]

            for attendee in attendees:
                email = unicode(attendee)
                # strip mailto: if it exists
                if email.lower().startswith('mailto:'):
                    email = email[7:]
                try:
                    name = attendee.params['CN']
                except KeyError:
                    name = None

                status_map = {'NEEDS-ACTION': 'noreply',
                              'ACCEPTED': 'yes',
                              'DECLINED': 'no',
                              'TENTATIVE': 'maybe'}
                status = 'noreply'
                try:
                    a_status = attendee.params['PARTSTAT']
                    status = status_map[a_status]
                except KeyError:
                    pass

                notes = None
                try:
                    guests = attendee.params['X-NUM-GUESTS']
                    notes = "Guests: {}".format(guests)
                except KeyError:
                    pass

                participants.append({'email': email,
                                     'name': name,
                                     'status': status,
                                     'notes': notes,
                                     'guests': []})

            location = component.get('location')
            organizer = component.get('organizer')
            if(organizer):
                organizer = unicode(organizer)
                if organizer.startswith('mailto:'):
                    organizer = organizer[7:]

            uid = str(component.get('uid'))
            event = Event(
                namespace=namespace,
                calendar=calendar,
                uid=uid,
                provider_name='ics',
                raw_data=component.to_ical(),
                title=title,
                description=description,
                location=location,
                reminders=str([]),
                recurrence=reccur,
                start=start,
                end=end,
                busy=True,
                all_day=all_day,
                read_only=True,
                source='local',
                participants=participants)

            events.append(event)
    return events


def import_attached_events(account_id, ics_str):
    """Import events from a file in the 'Attached Events' calendar."""

    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        assert account is not None

        calendar = db_session.query(Calendar).filter(
            Calendar.namespace_id == account.namespace.id,
            Calendar.name == 'Attached Events').first()
        if not calendar:
            calendar = Calendar(
                namespace_id=account.namespace.id,
                description='Attached Events',
                name='Attached Events')
            db_session.add(calendar)

        events = events_from_ics(account.namespace, calendar, ics_str)
        db_session.add(calendar)
        db_session.add_all(events)
        db_session.flush()
