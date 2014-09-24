from datetime import datetime, timedelta
from inbox.models import Event, Account

ACCOUNT_ID = 1
NAMESPACE_ID = 1
START = datetime.utcnow()
END = START + timedelta(0, 1)


def default_calendar(db):
    account = db.session.query(Account).filter(
        Account.id == ACCOUNT_ID).one()
    return account.default_calendar


def default_event(db):
    cal = default_calendar(db)
    ev = Event(namespace_id=NAMESPACE_ID,
               calendar=cal,
               title='title',
               description='',
               location='',
               busy=False,
               read_only=False,
               reminders='',
               recurrence='',
               start=START,
               end=END,
               all_day=False,
               provider_name='inbox',
               raw_data='',
               source='remote')

    db.session.add(ev)
    db.session.commit()
    return ev
