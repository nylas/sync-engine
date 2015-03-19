#!/usr/bin/env python
# Create an "Emailed events" for every account.

from inbox.models.session import session_scope
from inbox.models.account import Account


with session_scope() as db_session:
    accounts = db_session.query(Account)
    for account in accounts:
        account.create_emailed_events_calendar()
    db_session.commit()
