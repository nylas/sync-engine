
from inbox.models import Event
from default_event import default_event, default_calendar

ACCOUNT_ID = 1


def test_initial(db):
    remote = default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]

    local = Event(account_id=ACCOUNT_ID,
                  calendar=default_calendar(db),
                  provider_name='inbox', raw_data='',
                  read_only=False, all_day=False,
                  source='local')
    local.copy_from(remote)
    local.source = 'local'
    assert len(local.participants) == 3
    assert len(remote.participants) == 3
    db.session.add_all([local, remote])

    local.copy_from(remote)
    assert len(local.participants) == 3
    assert len(remote.participants) == 3


def test_no_change(db):
    local = default_event(db)
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = default_event(db)
    new.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 3
    assert len(new.participants) == 3
    assert len(remote.participants) == 3

    db.session.add_all([local, remote, new])


def test_add_participant_remote(db):
    local = default_event(db)
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = default_event(db)
    new.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'sarah@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 4
    assert len(new.participants) == 4
    assert len(remote.participants) == 4

    db.session.add_all([local, remote, new])


def test_add_participant_local(db):
    local = default_event(db)
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'sarah@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = default_event(db)
    new.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 4
    assert len(remote.participants) == 4

    db.session.add_all([local, remote, new])


def test_remove_participant_local(db):
    local = default_event(db)
    local.participant_list = [
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = default_event(db)
    new.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 2
    assert len(remote.participants) == 2

    db.session.add_all([local, remote, new])


def test_remove_participant_remote(db):
    local = default_event(db)
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = default_event(db)
    new.participant_list = [
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 2
    assert len(new.participants) == 2
    assert len(remote.participants) == 2

    db.session.add_all([local, remote, new])
