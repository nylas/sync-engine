import sys
import pytz
import arrow
import traceback
import icalendar
from datetime import datetime, date
from icalendar import Calendar as iCalendar

from flanker import mime
from html2text import html2text
from util import serialize_datetime, valid_base36
from timezones import timezones_table
from inbox.models.event import Event, EVENT_STATUSES
from inbox.events.util import MalformedEventError
from inbox.util.addr import canonicalize_address
from inbox.models.action_log import schedule_action

from inbox.log import get_logger
log = get_logger()


STATUS_MAP = {'NEEDS-ACTION': 'noreply',
              'ACCEPTED': 'yes',
              'DECLINED': 'no',
              'TENTATIVE': 'maybe'}
INVERTED_STATUS_MAP = {value: key for key, value in STATUS_MAP.iteritems()}


def events_from_ics(namespace, calendar, ics_str):
    try:
        cal = iCalendar.from_ical(ics_str)
    except (ValueError, IndexError, KeyError):
        raise MalformedEventError()

    events = dict(invites=[], rsvps=[])

    # See: https://tools.ietf.org/html/rfc5546#section-3.2
    calendar_method = None

    for component in cal.walk():
        if component.name == "VCALENDAR":
            calendar_method = component.get('method')

        if component.name == "VTIMEZONE":
            tzname = component.get('TZID')
            assert tzname in timezones_table,\
                "Non-UTC timezone should be in table"

        if component.name == "VEVENT":
            # Make sure the times are in UTC.
            try:
                original_start = component.get('dtstart').dt
                original_end = component.get('dtend').dt
            except AttributeError:
                raise MalformedEventError("Event lacks start and/or end time")

            start = original_start
            end = original_end
            original_start_tz = None

            all_day = False
            if isinstance(start, datetime) and isinstance(end, datetime):
                original_start_tz = str(original_start.tzinfo)

                # icalendar doesn't parse Windows timezones yet
                # (see: https://github.com/collective/icalendar/issues/44)
                # so we look if the timezone isn't in our Windows-TZ
                # to Olson-TZ table.
                if original_start.tzinfo is None:
                    tzid = component.get('dtstart').params.get('TZID', None)
                    assert tzid in timezones_table,\
                        "Non-UTC timezone should be in table"

                    corresponding_tz = timezones_table[tzid]
                    original_start_tz = corresponding_tz

                    local_timezone = pytz.timezone(corresponding_tz)
                    start = local_timezone.localize(original_start)

                if original_end.tzinfo is None:
                    tzid = component.get('dtend').params.get('TZID', None)
                    assert tzid in timezones_table,\
                        "Non-UTC timezone should be in table"

                    corresponding_tz = timezones_table[tzid]
                    local_timezone = pytz.timezone(corresponding_tz)
                    end = local_timezone.localize(original_end)

            elif isinstance(start, date) and isinstance(end, date):
                all_day = True
                start = arrow.get(start)
                end = arrow.get(end)

            assert type(start) == type(end), "Start and end should be of "\
                                             "the same type"

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
                assert last_modified is not None, \
                    "Event should have a DtStamp or LAST-MODIFIED timestamp"

            title = None
            summaries = component.get('summary', [])
            if not isinstance(summaries, list):
                summaries = [summaries]

            if summaries != []:
                title = " - ".join(summaries)

            description = unicode(component.get('description'))

            event_status = component.get('status')
            if event_status is not None:
                event_status = event_status.lower()
            else:
                # Some providers (e.g: iCloud) don't use the status field.
                # Instead they use the METHOD field to signal cancellations.
                method = component.get('method')
                if method and method.lower() == 'cancel':
                    event_status = 'cancelled'
                elif calendar_method and calendar_method.lower() == 'cancel':
                    # So, this particular event was not cancelled. Maybe the
                    # whole calendar was.
                    event_status = 'cancelled'
                else:
                    # Otherwise assume the event has been confirmed.
                    event_status = 'confirmed'

            assert event_status in EVENT_STATUSES

            recur = component.get('rrule')
            if recur:
                recur = "RRULE:{}".format(recur.to_ical())

            participants = []

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

            attendees = component.get('attendee', [])

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
            sequence_number = int(component.get('sequence'))

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
                recurrence=recur,
                start=start,
                end=end,
                busy=True,
                all_day=all_day,
                read_only=True,
                is_owner=is_owner,
                last_modified=last_modified,
                original_start_tz=original_start_tz,
                source='local',
                status=event_status,
                sequence_number=sequence_number,
                participants=participants)

            # We need to distinguish between invites/updates/cancellations
            # and RSVPs.
            if calendar_method == 'REQUEST' or calendar_method == 'CANCEL':
                events['invites'].append(event)
            elif calendar_method == 'REPLY':
                events['rsvps'].append(event)

    return events


def process_invites(db_session, message, account, invites):
    new_uids = [event.uid for event in invites]

    # Get the list of events which share a uid with those we received.
    # Note that we're limiting this query to events in the 'emailed events'
    # calendar, because that's where all the invites go.
    existing_events = db_session.query(Event).filter(
        Event.calendar_id == account.emailed_events_calendar_id,
        Event.namespace_id == account.namespace.id,
        Event.uid.in_(new_uids)).all()

    existing_events_table = {event.uid: event for event in existing_events}

    for event in invites:
        if event.uid not in existing_events_table:
            # This is some SQLAlchemy trickery -- the events returned
            # by events_from_ics aren't bound to a session yet. Because of
            # this, we don't care if they get garbage-collected. This is
            # important because we only want to keep events we haven't seen
            # yet --- updates are merged with the existing events and are
            # dropped immediately afterwards.

            # By associating the event to the message we make sure it
            # will be flushed to the db.
            event.calendar = account.emailed_events_calendar
            event.message = message
        else:
            # This is an event we already have in the db.
            # Let's see if the version we have is older or newer.
            existing_event = existing_events_table[event.uid]

            if existing_event.sequence_number <= event.sequence_number:
                merged_participants = existing_event.\
                    _partial_participants_merge(event)

                existing_event.update(event)
                existing_event.message = message

                # We have to do this mumbo-jumbo because MutableList does
                # not register changes to nested elements.
                # We could probably change MutableList to handle it (see:
                # https://groups.google.com/d/msg/sqlalchemy/i2SIkLwVYRA/mp2WJFaQxnQJ)
                # but this sounds very brittle.
                existing_event.participants = []
                for participant in merged_participants:
                    existing_event.participants.append(participant)


def _cleanup_nylas_uid(uid):
    uid = uid.lower()
    if '@nylas.com' in uid:
        return uid[:-10]

    return uid


def process_nylas_rsvps(db_session, message, account, rsvps):
    # The invite sending code generates invites with uids of the form
    # `public_id@nylas.com`. We couldn't use Event.uid for this because
    # it wouldn't work with Exchange (Exchange uids are of the form
    # 1:2323 and aren't guaranteed to be unique).
    new_uids = [_cleanup_nylas_uid(event.uid) for event in rsvps
                if '@nylas.com' in event.uid]

    # Drop uids which aren't base36 uids.
    new_uids = [uid for uid in new_uids if valid_base36(uid)]

    # Get the list of events which share a uid with those we received.
    # Note that we're excluding events from "Emailed events" because
    # we don't want to process RSVPs to invites we received.
    existing_events = db_session.query(Event).filter(
        Event.namespace_id == account.namespace.id,
        Event.calendar_id != account.emailed_events_calendar_id,
        Event.public_id.in_(new_uids)).all()

    existing_events_table = {event.public_id: event
                             for event in existing_events}

    for event in rsvps:
        event_uid = _cleanup_nylas_uid(event.uid)
        if event_uid not in existing_events_table:
            # We've received an RSVP to an event we never heard about. Save it,
            # maybe we'll sync the invite later.
            event.message = message
        else:
            # This is an event we already have in the db.
            existing_event = existing_events_table[event_uid]

            # Is the current event an update?
            if existing_event.sequence_number == event.sequence_number:
                merged_participants = existing_event.\
                    _partial_participants_merge(event)

                # We have to do this mumbo-jumbo because MutableList does
                # not register changes to nested elements.
                # We could probably change MutableList to handle it (see:
                # https://groups.google.com/d/msg/sqlalchemy/i2SIkLwVYRA/mp2WJFaQxnQJ)
                # but it seems very brittle.
                existing_event.participants = []
                for participant in merged_participants:
                    existing_event.participants.append(participant)

                # We need to sync back changes to the event manually
                if existing_event.calendar != account.emailed_events_calendar:
                    schedule_action('update_event', existing_event,
                                    existing_event.namespace.id, db_session,
                                    calendar_uid=existing_event.calendar.uid)

                db_session.flush()


def import_attached_events(db_session, account, message):
    """Import events from a file into the 'Emailed events' calendar."""

    assert account is not None
    from_addr = message.from_addr[0][1]

    # FIXME @karim - Don't import iCalendar events from messages we've sent.
    # This is only a stopgap measure -- what we need to have instead is
    # smarter event merging (i.e: looking at whether the sender is the
    # event organizer or not, and if the sequence number got incremented).
    if from_addr == account.email_address:
        return

    for part in message.attached_event_files:
        try:
            new_events = events_from_ics(account.namespace,
                                         account.emailed_events_calendar,
                                         part.block.data)
        except MalformedEventError:
            log.error('Attached event parsing error',
                      account_id=account.id, message_id=message.id,
                      logstash_tag='icalendar_autoimport',
                      invite=part.block.data)
            continue
        except (AssertionError, TypeError, RuntimeError,
                AttributeError, ValueError, UnboundLocalError,
                LookupError, ImportError, NameError):
            # Kind of ugly but we don't want to derail message
            # creation because of an error in the attached calendar.
            log.error('Unhandled exception during message parsing',
                      message_id=message.id,
                      invite=part.block.data,
                      logstash_tag='icalendar_autoimport',
                      traceback=traceback.format_exception(
                                    sys.exc_info()[0],
                                    sys.exc_info()[1],
                                    sys.exc_info()[2]))
            continue

        process_invites(db_session, message, account, new_events['invites'])

        # Gmail has a very very annoying feature: it doesn't use email to RSVP
        # to an invite sent by another gmail account. This makes it impossible
        # for us to update the event correctly. To work around this we let the
        # Gmail API handle invite sending. For other providers we process this
        # ourselves.
        # - karim
        if account.provider != 'gmail':
            process_nylas_rsvps(db_session, message, account, new_events['rsvps'])


def generate_icalendar_invite(event, invite_type='request'):
    # Generates an iCalendar invite from an event.
    assert invite_type in ['request', 'cancel']

    cal = iCalendar()
    cal.add('PRODID', '-//Nylas sync engine//nylas.com//')
    cal.add('METHOD', invite_type.upper())
    cal.add('VERSION', '2.0')
    cal.add('CALSCALE', 'GREGORIAN')

    icalendar_event = icalendar.Event()

    account = event.namespace.account
    organizer = icalendar.vCalAddress("MAILTO:{}".format(
            account.email_address))
    if account.name is not None:
        organizer.params['CN'] = account.name

    icalendar_event['organizer'] = organizer
    icalendar_event['sequence'] = str(event.sequence_number)
    icalendar_event['X-MICROSOFT-CDO-APPT-SEQUENCE'] = icalendar_event['sequence']

    if invite_type == 'cancel':
        icalendar_event['status'] = 'CANCELLED'
    else:
        icalendar_event['status'] = 'CONFIRMED'

    icalendar_event['uid'] = "{}@nylas.com".format(event.public_id)
    icalendar_event['last-modified'] = serialize_datetime(event.updated_at)
    icalendar_event['dtstamp'] = icalendar_event['last-modified']
    icalendar_event['created'] = serialize_datetime(event.created_at)
    icalendar_event['dtstart'] = serialize_datetime(event.start)
    icalendar_event['dtend'] = serialize_datetime(event.end)
    icalendar_event['transp'] = 'OPAQUE' if event.busy else 'TRANSPARENT'
    icalendar_event['description'] = event.description or ''
    icalendar_event['location'] = event.location or ''
    icalendar_event['summary'] = event.title or ''

    attendees = []
    for participant in event.participants:
        email = participant.get('email', None)

        # FIXME @karim: handle the case where a participant has no address.
        # We may have to patch the iCalendar module for this.
        assert email is not None and email != ""

        attendee = icalendar.vCalAddress("MAILTO:{}".format(email))
        name = participant.get('name', None)
        if name is not None:
            attendee.params['CN'] = name

        attendee.params['RSVP'] = 'TRUE'
        attendee.params['ROLE'] = 'REQ-PARTICIPANT'
        attendee.params['CUTYPE'] = 'INDIVIDUAL'

        status = participant.get('status', 'noreply')
        attendee.params['PARTSTAT'] = INVERTED_STATUS_MAP.get(status)
        attendees.append(attendee)

    if attendees != []:
        icalendar_event.add('ATTENDEE', attendees)

    cal.add_component(icalendar_event)
    return cal


def generate_invite_message(ical_txt, event, html_body, account,
                            invite_type='request'):

    assert invite_type in ['request', 'cancel']

    if invite_type == 'request':
        html_body = """<b>{title}</b><br>
        Start: {start}<br>
        End: {end}""".format(title=event.title, start=event.start, end=event.end)
    elif invite_type == 'cancel':
        html_body = """The event "{title}" has been cancelled.""".format(title=event.title)

    text_body = html2text(html_body)
    msg = mime.create.multipart('mixed')

    body = mime.create.multipart('alternative')

    # Why do we have a switch here? Because Exchange silently drops messages
    # which look too similar. Switching the order of headers seems to work.
    #
    # Oh, also Exchange strips our iCalendar file, so we add it as an
    # attachment to make sure it makes it through. Luckily, Gmail is smart
    # enough to cancel the event anyway.
    # - karim
    if invite_type == 'request':
        body.append(
            mime.create.text('plain', text_body),
            mime.create.text('html', html_body),
            mime.create.text('calendar; method=REQUEST'.format(invite_type),
                             ical_txt, charset='utf8'))
        msg.append(body)
    elif invite_type == 'cancel':
        body.append(
           mime.create.text('html', html_body),
           mime.create.text('plain', text_body),
           mime.create.text('calendar; method=CANCEL'.format(invite_type),
                            ical_txt, charset='utf8'))
        msg.append(body)

        attachment = mime.create.attachment(
                         'application/ics',
                         ical_txt,
                         'invite.ics',
                         disposition='attachment')
        msg.append(attachment)

    msg.headers['From'] = account.email_address
    msg.headers['Reply-To'] = account.email_address

    if invite_type == 'request':
        msg.headers['Subject'] = "Invitation: {}".format(event.title)
    elif invite_type == 'cancel':
        msg.headers['Subject'] = "Cancelled: {}".format(event.title)

    return msg


def send_invite(ical_txt, event, html_body, account, invite_type='request'):
    from inbox.sendmail.base import get_sendmail_client, SendMailException

    for participant in event.participants:
        email = participant.get('email', None)
        if email is None:
            continue

        msg = generate_invite_message(ical_txt, event, html_body, account,
                                      invite_type)
        msg.headers['To'] = email
        final_message = msg.to_string()

        try:
            sendmail_client = get_sendmail_client(account)
            sendmail_client.send_generated_email([email], final_message)
        except SendMailException as e:
            log.error("Couldnt send invite email for", email_address=email,
                      event_id=event.id, account_id=account.id,
                      logstash_tag='invite_sending', exception=str(e))

        if account.provider == 'eas' and invite_type == 'request':
            # Exchange very surprisingly goes out of the way to send an invite
            # to all participants.
            # We only do this for invites and not cancelled because of the
            # Exchange doesn't parse our cancellation messages as invites.
            break
