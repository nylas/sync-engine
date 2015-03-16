import pytz
from datetime import datetime, date
from icalendar import Calendar as iCalendar

from inbox.models.account import Account
from inbox.models.event import Event
from inbox.models.calendar import Calendar
from inbox.models.session import session_scope
from inbox.events.util import MalformedEventError
from timezones import timezones_table


STATUS_MAP = {'NEEDS-ACTION': 'noreply',
              'ACCEPTED': 'yes',
              'DECLINED': 'no',
              'TENTATIVE': 'maybe'}


def _remove_tz(d):
    if d.tzinfo:
        d = d.astimezone(pytz.utc).replace(tzinfo=None)
    return d


def events_from_ics(namespace, calendar, ics_str):
    try:
        cal = iCalendar.from_ical(ics_str)
    except ValueError:
        raise MalformedEventError()

    events = []

    for component in cal.walk():
        if component.name == "VTIMEZONE":
            tzname = component.get('TZID')
            assert tzname in timezones_table,\
                 "Non-UTC timezone should be in table"

        if component.name == "VEVENT":
            # Make sure the times are in UTC.
            original_start = component.get('dtstart').dt
            original_end = component.get('dtend').dt

            start = original_start
            end = original_end

            if isinstance(start, datetime) and isinstance(end, datetime):
                all_day = False
                # icalendar doesn't parse Windows timezones yet (see: https://github.com/collective/icalendar/issues/44)
                # so we look if the timezone isn't in our Windows-TZ
                # to Olson-TZ table.
                if original_start.tzinfo is None:
                    tzid = component.get('dtstart').params.get('TZID', None)
                    assert tzid in timezones_table,\
                         "Non-UTC timezone should be in table"

                    corresponding_tz = timezones_table[tzid]
                    local_timezone = pytz.timezone(corresponding_tz)
                    start = local_timezone.localize(original_start)

                if original_end.tzinfo is None:
                    tzid = component.get('dtend').params.get('TZID', None)
                    assert tzid in timezones_table, "Non-UTC timezone should be in table"

                    corresponding_tz = timezones_table[tzid]
                    local_timezone = pytz.timezone(corresponding_tz)
                    end = local_timezone.localize(original_end)

                # MySQL doesn't like localized datetimes.
                start = _remove_tz(start)
                end = _remove_tz(end)
            elif isinstance(start, date) and isinstance(end, date):
                all_day = True
                start = datetime.combine(start, datetime.min.time())
                end = datetime.combine(end, datetime.min.time())

            title = component.get('summary')
            description = unicode(component.get('description'))

            reccur = component.get('rrule')
            if reccur:
                reccur = reccur.to_ical()
            else:
                reccur = ''
            participants = []
            attendees = component.get('attendee')

            organizer = component.get('organizer')
            if organizer:
                organizer = unicode(organizer)
                if organizer.startswith('mailto:'):
                    organizer = organizer[7:]

            # FIXME: canonicalize email address too
            if namespace.account.email_address == organizer:
                is_owner = True
            else:
                is_owner = False

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
                is_owner=is_owner,
                source='local',
                participants=participants)

            events.append(event)
    return events


def import_attached_events(account_id, ics_str):
    """Import events from a file in the 'Events emailed to' calendar."""

    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        assert account is not None

        calname = "Events emailed to {}".format(account.email_address)
        calendar = db_session.query(Calendar).filter(
            Calendar.namespace_id == account.namespace.id,
            Calendar.name == calname).first()

        events = events_from_ics(account.namespace, calendar, ics_str)
        db_session.add_all(events)
        db_session.flush()
