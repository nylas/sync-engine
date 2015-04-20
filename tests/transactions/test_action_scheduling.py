from inbox.models.action_log import schedule_action, ActionLog

from tests.util.base import add_fake_event


def test_action_scheduling(db, default_account):
    event = add_fake_event(db.session, default_account.namespace.id)

    schedule_action('create_event', event, default_account.namespace.id,
                    db.session)
    db.session.commit()

    entry = db.session.query(ActionLog).filter(
        ActionLog.namespace_id == default_account.namespace.id,
        ActionLog.action == 'create_event').one()

    assert entry.discriminator == 'actionlog'
    assert entry.table_name == 'event' and entry.record_id == event.id
    assert not entry.extra_args

    schedule_action('delete_event', event, default_account.namespace.id,
                    db.session, event_uid=event.uid,
                    calendar_name=event.calendar.name,
                    calendar_uid=event.calendar.uid)
    db.session.commit()

    entry = db.session.query(ActionLog).filter(
        ActionLog.namespace_id == default_account.namespace.id,
        ActionLog.action == 'delete_event').one()

    assert entry.discriminator == 'actionlog'
    assert entry.table_name == 'event' and entry.record_id == event.id
    assert entry.extra_args == \
        dict(event_uid=event.uid, calendar_name=event.calendar.name,
             calendar_uid=event.calendar.uid)
