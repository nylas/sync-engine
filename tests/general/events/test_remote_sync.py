import pytest

from tests.util.base import config
from tests.general.events.conftest import EventsProviderStub

# Need to set up test config before we can import from
# inbox.models.tables.
config()
from inbox.models import Account, Event
from inbox.events.remote_sync import EventSync
from inbox.util.misc import MergeError

ACCOUNT_ID = 1

# STOPSHIP(emfree): Test multiple distinct remote providers


@pytest.fixture(scope='function')
def alt_event_sync(config, db):
    return EventSync(2)


@pytest.fixture(scope='function')
def alternate_events_provider(config, db):
    return EventsProviderStub('alternate_provider')


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


def test_merge(db, config, event_sync):
    """Test the basic logic of the merge() function."""
    base = _default_event(db)
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
                   source='remote')

    dest = _default_event(db)

    dest.merge_from(base, remote)
    assert dest.subject == 'new subject'
    assert dest.body == 'new body'
    assert dest.location == 'new location'
    assert dest.busy
    assert dest.read_only
    assert dest.start == 2
    assert dest.end == 3


def test_merge_conflict(db, config, event_sync):
    """Test that merge() raises an error on conflict."""
    base = _default_event(db)

    remote = Event(account_id=ACCOUNT_ID,
                   calendar=_default_calendar(db),
                   subject='new subject',
                   body='new body',
                   location='new location',
                   busy=False,
                   read_only=True,
                   reminders='',
                   recurrence='',
                   start=2,
                   end=3,
                   all_day=False,
                   source='remote')

    dest = Event(account_id=ACCOUNT_ID,
                 calendar=_default_calendar(db),
                 subject='subject2',
                 body='body2',
                 location='location2',
                 busy=False,
                 read_only=False,
                 reminders='',
                 recurrence='',
                 start=0,
                 end=1,
                 all_day=False,
                 source='remote')

    with pytest.raises(MergeError):
        dest.merge_from(base, remote)

    # Check no update in case of conflict
    assert dest.subject == 'subject2'
    assert dest.body == 'body2'
    assert dest.location == 'location2'


def test_add_events(events_provider, event_sync, db):
    """Test that added events get stored."""
    num_original_local_events = db.session.query(Event). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='local').count()
    num_original_remote_events = db.session.query(Event). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='remote').count()
    events_provider.supply_event('subj')
    events_provider.supply_event('subj2')

    event_sync.provider_instance = events_provider
    event_sync.poll()
    num_current_local_events = db.session.query(Event). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='local').count()
    num_current_remote_events = db.session.query(Event). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='remote').count()
    assert num_current_local_events - num_original_local_events == 2
    assert num_current_remote_events - num_original_remote_events == 2


def test_update_event(events_provider, event_sync, db):
    """Test that subsequent event updates get stored."""
    events_provider.supply_event('subj', '')
    event_sync.provider_instance = events_provider
    event_sync.poll()
    results = db.session.query(Event).filter_by(source='remote').all()
    db.new_session()
    subjects = [r.subject for r in results]
    assert 'subj' in subjects

    events_provider.__init__()
    events_provider.supply_event('newsubj', 'newbody')
    event_sync.poll()
    db.new_session()

    results = db.session.query(Event).filter_by(source='remote').all()
    subjs = [r.subject for r in results]
    assert 'newsubj' in subjs
    bodies = [r.body for r in results]
    assert 'newbody' in bodies


def test_uses_local_updates(events_provider, event_sync, db):
    """Test that non-conflicting local and remote updates to the same event
    both get stored."""
    events_provider.supply_event('subj', '')
    event_sync.provider_instance = events_provider
    event_sync.poll()
    results = db.session.query(Event).filter_by(source='local').all()
    # Fake a local event update.
    results[-1].subject = 'New Subject'
    db.session.commit()

    events_provider.__init__()
    events_provider.supply_event('subj', 'newbody')
    event_sync.provider_instance = events_provider
    event_sync.poll()

    remote_results = db.session.query(Event).filter_by(source='remote').all()
    subjects = [r.subject for r in remote_results]
    assert 'New Subject' in subjects
    bodies = [r.body for r in remote_results]
    assert 'newbody' in bodies

    local_results = db.session.query(Event).filter_by(source='local').all()
    subjects = [r.subject for r in local_results]
    assert 'New Subject' in subjects
    bodies = [r.body for r in local_results]
    assert 'newbody' in bodies


def test_multiple_remotes(events_provider, alternate_events_provider,
                          event_sync, db):
    events_provider.supply_event('subj', '')
    alternate_events_provider.supply_event('subj2', 'body')

    event_sync.provider_instance = events_provider
    event_sync.poll()

    event_sync.provider_instance = alternate_events_provider
    event_sync.poll()

    result = db.session.query(Event). \
        filter_by(source='local', provider_name='test_provider').one()
    alternate_result = db.session.query(Event). \
        filter_by(source='local', provider_name='alternate_provider').one()
    # Check that both events were persisted, even though they have the same
    # uid.
    assert result.subject == 'subj'
    assert alternate_result.subject == 'subj2'


def test_deletes(events_provider, event_sync, db):
    num_original_events = db.session.query(Event).count()
    events_provider.supply_event('subj')
    event_sync.provider_instance = events_provider
    event_sync.poll()
    num_current_events = db.session.query(Event).count()
    assert num_current_events - num_original_events == 2

    events_provider.__init__()
    events_provider.supply_event('subj', deleted=True)
    event_sync.poll()

    num_current_events = db.session.query(Event).count()
    assert num_current_events == num_original_events


def test_malformed(events_provider, event_sync, db):
    num_original_events = db.session.query(Event).count()
    events_provider.supply_bad()
    event_sync.provider_instance = events_provider
    event_sync.poll()
    assert db.session.query(Event).count() == num_original_events
