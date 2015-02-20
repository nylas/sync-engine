import pytest
from datetime import datetime

from tests.util.base import config
from tests.general.events.conftest import EventsProviderStub, GoogleServiceStub

# Need to set up test config before we can import from
# inbox.models.tables.
config()
from inbox.models import Event
from inbox.events.remote_sync import EventSync
from inbox.events.google import GoogleEventsProvider
from inbox.util.misc import MergeError
from default_event import default_event

NAMESPACE_ID = 1

# STOPSHIP(emfree): Test multiple distinct remote providers


@pytest.fixture(scope='function')
def alt_event_sync(config, db):
    return EventSync('inboxapptest@gmail.com', 'gmail', 2, 2)


@pytest.fixture(scope='function')
def alternate_events_provider(config, db):
    return EventsProviderStub('alternate_provider')


def test_merge(db, config, event_sync):
    """Test the basic logic of the merge() function."""
    base = default_event(db.session)
    remote = default_event(db.session)
    remote.title = 'new title'
    remote.description = 'new description'
    remote.location = 'new location'

    dest = default_event(db.session)

    dest.merge_from(base, remote)
    assert dest.title == 'new title'
    assert dest.description == 'new description'
    assert dest.location == 'new location'
    assert dest.read_only is False
    assert dest.start == base.start
    assert dest.end == base.end


def test_merge_conflict(db, config, event_sync):
    """Test that merge() raises an error on conflict."""
    base = default_event(db.session)

    remote = default_event(db.session)

    remote.title = 'new title'
    remote.description = 'new description'
    remote.location = 'new location'

    dest = default_event(db.session)
    dest.title = 'title2'
    dest.description = 'description2'
    dest.location = 'location2'

    with pytest.raises(MergeError):
        dest.merge_from(base, remote)

    # Check no update in case of conflict
    assert dest.title == 'title2'
    assert dest.description == 'description2'
    assert dest.location == 'location2'


def test_add_events(events_provider, event_sync, db):
    """Test that added events get stored."""
    num_original_local_events = db.session.query(Event). \
        filter_by(namespace_id=NAMESPACE_ID).filter_by(source='local').count()
    num_original_remote_events = db.session.query(Event). \
        filter_by(namespace_id=NAMESPACE_ID).filter_by(source='remote').count()
    events_provider.supply_event('subj')
    events_provider.supply_event('subj2')

    event_sync.provider = events_provider
    event_sync.sync()
    num_current_local_events = db.session.query(Event). \
        filter_by(namespace_id=NAMESPACE_ID).filter_by(source='local').count()
    num_current_remote_events = db.session.query(Event). \
        filter_by(namespace_id=NAMESPACE_ID).filter_by(source='remote').count()
    assert num_current_local_events - num_original_local_events == 2
    assert num_current_remote_events - num_original_remote_events == 2


def test_update_event(events_provider, event_sync, db):
    """Test that subsequent event updates get stored."""
    events_provider.supply_event('subj', '')
    event_sync.provider = events_provider
    event_sync.sync()
    results = db.session.query(Event).filter_by(source='remote').all()
    titles = [r.title for r in results]
    assert 'subj' in titles

    events_provider.__init__()
    events_provider.supply_event('newsubj', 'newdescription')
    event_sync.sync()
    db.session.commit()

    results = db.session.query(Event).filter_by(source='remote').all()
    subjs = [r.title for r in results]
    assert 'newsubj' in subjs
    bodies = [r.description for r in results]
    assert 'newdescription' in bodies


def test_uses_local_updates(events_provider, event_sync, db):
    """Test that non-conflicting local and remote updates to the same event
    both get stored."""
    events_provider.supply_event('subj', '')
    event_sync.provider = events_provider
    event_sync.sync()
    results = db.session.query(Event).filter_by(source='local').all()
    # Fake a local event update.
    results[-1].title = 'New title'
    db.session.commit()

    events_provider.__init__()
    events_provider.supply_event('subj', 'newdescription')
    event_sync.provider = events_provider
    event_sync.sync()

    remote_results = db.session.query(Event).filter_by(source='remote').all()
    titles = [r.title for r in remote_results]
    assert 'New title' in titles
    bodies = [r.description for r in remote_results]
    assert 'newdescription' in bodies

    local_results = db.session.query(Event).filter_by(source='local').all()
    titles = [r.title for r in local_results]
    assert 'New title' in titles
    bodies = [r.description for r in local_results]
    assert 'newdescription' in bodies


def test_multiple_remotes(events_provider, alternate_events_provider,
                          event_sync, db):
    events_provider.supply_event('subj', '')
    alternate_events_provider.supply_event('subj2', 'description')

    event_sync.provider = events_provider
    event_sync.sync()

    event_sync.provider = alternate_events_provider
    event_sync.sync()

    result = db.session.query(Event). \
        filter_by(source='local', provider_name='test_provider').one()
    alternate_result = db.session.query(Event). \
        filter_by(source='local', provider_name='alternate_provider').one()
    # Check that both events were persisted, even though they have the same
    # uid.
    assert result.title == 'subj'
    assert alternate_result.title == 'subj2'


def test_deletes(events_provider, event_sync, db):
    num_original_events = db.session.query(Event).count()
    events_provider.supply_event('subj')
    event_sync.provider = events_provider
    event_sync.sync()
    num_current_events = db.session.query(Event).count()
    assert num_current_events - num_original_events == 2

    events_provider.__init__()
    events_provider.supply_event('subj', deleted=True)
    event_sync.sync()

    num_current_events = db.session.query(Event).count()
    assert num_current_events == num_original_events


def test_malformed(events_provider, event_sync, db):
    num_original_events = db.session.query(Event).count()
    events_provider.supply_bad()
    event_sync.provider = events_provider
    event_sync.sync()
    assert db.session.query(Event).count() == num_original_events


def test_minimum_modification():
    provider = GoogleEventsProvider(1, 1)
    # Use a Google service stand-in that requires removing the minimum
    # modification time to work.
    provider._get_google_service = lambda: GoogleServiceStub(410)
    twenty_fourteen = datetime(2014, 1, 1, 0, 0, 0, 0)
    (_, cal, _) = provider.fetch_calendar_items(
        'bob', 1, sync_from_dt=twenty_fourteen).next()
    assert cal is True


def test_minimum_modification_passthrough():
    # Test that non-410 errors don't get swallowed.
    provider = GoogleEventsProvider(1, 1)
    # Use a Google service stand-in that requires removing the minimum
    # modification time to work.
    provider._get_google_service = lambda: GoogleServiceStub(400)
    with pytest.raises(Exception) as excinfo:
        twenty_fourteen = datetime(2014, 1, 1, 0, 0, 0, 0)
        (_, cal, _) = provider.fetch_calendar_items(
            'bob', 1, sync_from_dt=twenty_fourteen).next()
    assert excinfo.typename == 'HttpError'
