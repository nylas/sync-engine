
from inbox.models import Event

ACCOUNT_ID = 1


def _default_event():
    return Event(account_id=ACCOUNT_ID,
                 subject='subject',
                 body='',
                 location='',
                 busy=False,
                 locked=False,
                 reminders='',
                 recurrence='',
                 start=0,
                 end=1,
                 all_day=False,
                 time_zone=0,
                 source='remote')


def test_initial(db):
    remote = _default_event()
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]

    local = Event()
    local.copy_from(remote)
    local.source = 'local'
    assert len(local.participants) == 3
    assert len(remote.participants) == 3
    db.session.add_all([local, remote])

    local.copy_from(remote)
    assert len(local.participants) == 3
    assert len(remote.participants) == 3


def test_no_change(db):
    local = _default_event()
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    remote = _default_event()
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    new = _default_event()
    new.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 3
    assert len(new.participants) == 3
    assert len(remote.participants) == 3

    db.session.add_all([local, remote, new])


def test_add_participant_remote(db):
    local = _default_event()
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    remote = _default_event()
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    new = _default_event()
    new.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'sarah@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 4
    assert len(new.participants) == 4
    assert len(remote.participants) == 4

    db.session.add_all([local, remote, new])


def test_add_participant_local(db):
    local = _default_event()
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'sarah@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    remote = _default_event()
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    new = _default_event()
    new.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 4
    assert len(remote.participants) == 4

    db.session.add_all([local, remote, new])


def test_remove_participant_local(db):
    local = _default_event()
    local.participant_list = [
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    remote = _default_event()
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    new = _default_event()
    new.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 2
    assert len(remote.participants) == 2

    db.session.add_all([local, remote, new])


def test_remove_participant_remote(db):
    local = _default_event()
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    remote = _default_event()
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'awaiting'},
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]
    new = _default_event()
    new.participant_list = [
        {'email': 'paul@example.com',
         'status': 'awaiting'},
        {'email': 'mary@example.com',
         'status': 'awaiting'}]

    local.merge_from(remote, new)
    remote.copy_from(local)

    assert len(local.participants) == 2
    assert len(new.participants) == 2
    assert len(remote.participants) == 2

    db.session.add_all([local, remote, new])
