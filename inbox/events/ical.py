import pytz
from datetime import datetime, date
from icalendar import Calendar as iCalendar

from inbox.models.event import Event
from inbox.models.calendar import Calendar
from inbox.models.session import session_scope
from inbox.events.util import MalformedEventError
from inbox.util.addr import canonicalize_address
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
                # icalendar doesn't parse Windows timezones yet
                # (see: https://github.com/collective/icalendar/issues/44)
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
                    assert tzid in timezones_table,\
                        "Non-UTC timezone should be in table"

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

            # Get the last modification date.
            # Exchange uses DtStamp, iCloud and Gmail LAST-MODIFIED.
            last_modified_tstamp = component.get('dtstamp')
            last_modified = None
            if last_modified_tstamp is not None:
                # This is one surprising instance of Exchange doing
                # the right thing by giving us an UTC timestamp. Also note that
                # Google calendar also include the DtStamp field, probably to
                # be a good citizen.
                if last_modified_tstamp.dt.tzinfo is not None:
                    last_modified = last_modified_tstamp.dt
                else:
                    raise NotImplementedError("We don't support arcane Windows"
                                              " timezones in timestamps yet")
            else:
                # Try to look for a LAST-MODIFIED element instead.
                # Note: LAST-MODIFIED is always in UTC.
                # http://www.kanzaki.com/docs/ical/lastModified.html
                last_modified = component.get('last-modified').dt
                assert last_modified is not None,\
                 "Event should have a DtStamp or LAST-MODIFIED timestamp"

            last_modified = _remove_tz(last_modified)
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
                # Here's the problem. Gmail and Exchange define the organizer
                # field like this:
                #
                # ORGANIZER;CN="User";EMAIL="user@email.com":mailto:user@email.com
                # but iCloud does it like this:
                # ORGANIZER;CN=User;EMAIL=user@icloud.com:mailto:
                # random_alphanumeric_string@imip.me.com
                # so what we first try to get the EMAIL field, and only if
                # it's not present we use the MAILTO: link.
                if 'EMAIL' in organizer.params:
                    organizer = organizer.params['EMAIL']
                else:
                    organizer = unicode(organizer)
                    if organizer.startswith('mailto:'):
                        organizer = organizer[7:]

            if (namespace.account.email_address ==
                    canonicalize_address(organizer)):
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
                last_modified=last_modified,
                source='local',
                participants=participants)

            events.append(event)
    return events


def import_attached_events(account_id, ics_str):
    """Import events from a file into the 'Emailed events' calendar."""
    from inbox.models.account import Account

    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        assert account is not None

        calendar = db_session.query(Calendar).filter(
            Calendar.namespace_id == account.namespace.id,
            Calendar.name == "Emailed events").one()

        new_events = events_from_ics(account.namespace, calendar, ics_str)
        uids_table = {event.uid: event for event in new_events}

        # Get the list of events which share a uid with those we received.
        existing_events = db_session.query(Event).filter(
            Event.calendar_id == calendar.id,
            Event.namespace_id == account.namespace.id,
            Event.uid.in_(uids_table.keys())).all()

        existing_events_table = {event.uid: event for event in existing_events}

        to_add = []
        for event in new_events:
            if event.uid not in existing_events_table:
                to_add.append(event)
            else:
                # This is an event we already have in the db.
                # Let's see if the version we have is older or newer.
                existing_event = existing_events_table[event.uid]
                if event.last_modified > existing_event.last_modified:
                    existing_event.update(event)
        db_session.add_all(to_add)
        db_session.flush()
