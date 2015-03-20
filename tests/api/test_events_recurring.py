import arrow
import urllib
from inbox.models import Account, Event, Calendar
from tests.util.base import api_client

__all__ = ['api_client']


ACCOUNT_ID = 1


def add_recurring_event(db, account):
    rrule = ["RRULE:FREQ=WEEKLY"]
    ev = db.session.query(Event).filter_by(uid='recurapitest').first()
    if ev:
        db.session.delete(ev)
    cal = db.session.query(Calendar).filter_by(
        namespace_id=account.namespace.id).order_by('id').first()
    ev = Event(namespace_id=account.namespace.id,
               calendar=cal,
               title='recurring-weekly',
               description='',
               uid='recurapitest',
               location='',
               busy=False,
               read_only=False,
               reminders='',
               recurrence=rrule,
               start=arrow.get(2015, 3, 17, 1, 30, 00),
               end=arrow.get(2015, 3, 17, 1, 45, 00),
               all_day=False,
               is_owner=True,
               participants=[],
               provider_name='inbox',
               raw_data='',
               original_start_tz='America/Los_Angeles',
               original_start_time=None,
               master_event_uid=None,
               source='local')
    db.session.add(ev)
    db.session.commit()
    return ev


def test_api_expand_recurring(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    event = add_recurring_event(db, acct)

    # 3 existing test events in database + 1 new one
    events = api_client.get_data('/events?expand_recurring=false', ns_id)
    assert len(events) == 4
    # Make sure the recurrence info is on the recurring event
    for e in events:
        if e['title'] == 'recurring-weekly':
            assert e.get('recurrence') is not None

    thirty_weeks = event.start.replace(weeks=+30).isoformat()
    starts_after = event.start.replace(days=-1).isoformat()
    recur = 'expand_recurring=true&starts_after={}&ends_before={}'.format(
        urllib.quote_plus(starts_after), urllib.quote_plus(thirty_weeks))
    all_events = api_client.get_data('/events?' + recur, ns_id)
    assert len(all_events) == 30

    # the ordering should be correct
    prev = all_events[0]['when']['start_time']
    for e in all_events[1:]:
        assert e['when']['start_time'] > prev
        prev = e['when']['start_time']

    events = api_client.get_data('/events?' + recur + '&limit=5', ns_id)
    assert len(events) == 5

    events = api_client.get_data('/events?' + recur + '&offset=5', ns_id)
    assert events[0]['id'] == all_events[5]['id']

    events = api_client.get_data('/events?' + recur + '&view=count', ns_id)
    assert events.get('count') == 30


def urlsafe(dt):
    return urllib.quote_plus(dt.isoformat())


def test_api_expand_recurring_before_after(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    event = add_recurring_event(db, acct)

    starts_after = event.start.replace(weeks=+15)
    ends_before = starts_after.replace(days=+1)

    recur = 'expand_recurring=true&starts_after={}&ends_before={}'.format(
        urlsafe(starts_after), urlsafe(ends_before))
    all_events = api_client.get_data('/events?' + recur, ns_id)
    assert len(all_events) == 1

    recur = 'expand_recurring=true&starts_after={}&starts_before={}'.format(
        urlsafe(starts_after), urlsafe(ends_before))
    all_events = api_client.get_data('/events?' + recur, ns_id)
    assert len(all_events) == 1

    recur = 'expand_recurring=true&ends_after={}&starts_before={}'.format(
        urlsafe(starts_after), urlsafe(ends_before))
    all_events = api_client.get_data('/events?' + recur, ns_id)
    assert len(all_events) == 1

    recur = 'expand_recurring=true&ends_after={}&ends_before={}'.format(
        urlsafe(starts_after), urlsafe(ends_before))
    all_events = api_client.get_data('/events?' + recur, ns_id)
    assert len(all_events) == 1


def test_api_override_serialization(db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id
    event = add_recurring_event(db, acct)

    override = Event(original_start_time=event.start,
                     master_event_uid=event.uid,
                     namespace_id=acct.namespace.id,
                     calendar_id=event.calendar_id)
    override.update(event)
    override.uid = event.uid + "_" + event.start.strftime("%Y%m%dT%H%M%SZ")
    override.master = event
    override.master_event_uid = event.uid
    override.cancelled = True
    db.session.add(override)
    db.session.commit()

    filter = 'starts_after={}&ends_before={}'.format(
        urlsafe(event.start.replace(hours=-1)),
        urlsafe(event.start.replace(weeks=+1)))
    events = api_client.get_data('/events?' + filter, ns_id)
    # We should have the base event and the override back, but no extras;
    # this allows clients to do their own expansion, should they ever desire
    # to experience the joy that is RFC 2445 section 4.8.5.4.
    assert len(events) == 2
    assert events[0].get('object') == 'event'
    assert events[0].get('recurrence') is not None
    assert events[1].get('object') == 'event'
    assert events[1].get('cancelled') is True
