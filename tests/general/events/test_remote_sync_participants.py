from tests.util.base import config

# Need to set up test config before we can import from
# inbox.models.tables.
config()
from inbox.models import Account, Event, Participant

ACCOUNT_ID = 1

# STOPSHIP(emfree): Test multiple distinct remote providers


def _default_calendar(db):
    account = db.session.query(Account).filter(
        Account.id == ACCOUNT_ID).one()
    return account.default_calendar


def _default_event(db):
    return Event(account_id=ACCOUNT_ID,
                 calendar=_default_calendar(db),
                 subject='subject',
                 body='',
                 location='',
                 busy=False,
                 read_only=False,
                 reminders='',
                 recurrence='',
                 start=0,
                 end=1,
                 all_day=False,
                 source='remote')


def test_add_participant(db, config):
    """Test the basic logic of the merge() function."""
    base = _default_event(db)
    participant = Participant(email_address="foo@example.com")
    remote = Event(account_id=ACCOUNT_ID,
                   calendar=_default_calendar(db),
                   subject='new subject',
                   body='new body',
                   location='new location',
                   busy=True,
                   read_only=True,
                   reminders='',
                   recurrence='',
                   start=2,
                   end=3,
                   all_day=False,
                   source='remote',
                   participants=[participant])

    dest = _default_event(db)

    dest.merge_from(base, remote)
    assert len(dest.participants) == 1


def test_update_participant_status(db, config):
    """Test the basic logic of the merge() function."""
    base = _default_event(db)
    base.participants = [Participant(email_address="foo@example.com")]

    dest = _default_event(db)
    dest.participants = [Participant(email_address="foo@example.com")]

    participant1 = Participant(email_address="foo@example.com",
                               status="yes")
    remote = Event(account_id=ACCOUNT_ID,
                   calendar=_default_calendar(db),
                   subject='new subject',
                   body='new body',
                   location='new location',
                   busy=True,
                   read_only=True,
                   reminders='',
                   recurrence='',
                   start=2,
                   end=3,
                   all_day=False,
                   source='remote',
                   participants=[participant1])

    dest.merge_from(base, remote)
    assert len(dest.participants) == 1
    assert dest.participants[0].status == 'yes'


def test_update_participant_status2(db, config):
    """Test the basic logic of the merge() function."""
    base = _default_event(db)
    base.participants = [Participant(email_address="foo@example.com",
                                     status="no")]

    dest = _default_event(db)
    dest.participants = [Participant(email_address="foo@example.com",
                                     status="no")]

    participant1 = Participant(email_address="foo@example.com",
                               status="yes")
    remote = Event(account_id=ACCOUNT_ID,
                   calendar=_default_calendar(db),
                   subject='new subject',
                   body='new body',
                   location='new location',
                   busy=True,
                   read_only=True,
                   reminders='',
                   recurrence='',
                   start=2,
                   end=3,
                   all_day=False,
                   source='remote',
                   participants=[participant1])

    dest.merge_from(base, remote)
    assert len(dest.participants) == 1
    assert dest.participants[0].status == 'yes'


def test_multi_update(db, config):
    """Test the basic logic of the merge() function."""
    base = _default_event(db)
    base.participants = [Participant(email_address="foo@example.com",
                                     status="no")]

    dest = _default_event(db)
    dest.participants = [Participant(email_address="foo@example.com",
                                     status="no"),
                         Participant(email_address="foo2@example.com",
                                     status="no")]

    participant1 = Participant(email_address="foo@example.com",
                               status="yes")
    remote = Event(account_id=ACCOUNT_ID,
                   calendar=_default_calendar(db),
                   subject='new subject',
                   body='new body',
                   location='new location',
                   busy=True,
                   read_only=True,
                   reminders='',
                   recurrence='',
                   start=2,
                   end=3,
                   all_day=False,
                   source='remote',
                   participants=[participant1])

    dest.merge_from(base, remote)
    assert len(dest.participants) == 2
    for p in dest.participants:
        if p.email_address == "foo@example.com":
            assert p.status == "yes"
        if p.email_address == "foo2@example.com":
            assert p.status == "no"
