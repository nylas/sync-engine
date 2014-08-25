
from inbox.models import Event, Account

ACCOUNT_ID = 1


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


def test_initial(db):
    remote = _default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]

    local = Event(account_id=ACCOUNT_ID,
                  calendar=_default_calendar(db))
    local.copy_from(remote)
    local.source = 'local'
    assert len(local.participants) == 3
    assert len(remote.participants) == 3
    db.session.add_all([local, remote])

    local.copy_from(remote)
    assert len(local.participants) == 3
    assert len(remote.participants) == 3


def test_no_change(db):
    local = _default_event(db)
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = _default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = _default_event(db)
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
    local = _default_event(db)
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = _default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = _default_event(db)
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
    local = _default_event(db)
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'sarah@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = _default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = _default_event(db)
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
    local = _default_event(db)
    local.participant_list = [
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = _default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = _default_event(db)
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
    local = _default_event(db)
    local.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    remote = _default_event(db)
    remote.participant_list = [
        {'email': 'peter@example.com',
         'status': 'noreply'},
        {'email': 'paul@example.com',
         'status': 'noreply'},
        {'email': 'mary@example.com',
         'status': 'noreply'}]
    new = _default_event(db)
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
