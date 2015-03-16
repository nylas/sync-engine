#!/usr/bin/env python
# Create an "Events emailed to <addr>" for every account.

from inbox.models.session import session_scope
from inbox.models.account import Account
from inbox.models.calendar import Calendar

with session_scope() as db_session:
    accounts = db_session.query(Account)
    for account in accounts:
        calname = "Events emailed to {}".format(account.email_address)
        cal = db_session.query(Calendar).filter(
                Calendar.namespace_id == account.namespace.id,
                Calendar.description == calname).first()
        if cal is None:
            print "Creating 'Events emailed' calendar for {}".format(
                    account.email_address)
            cal = Calendar(namespace_id=account.namespace.id,
                           description=calname,
                           uid='inbox',
                           name=calname,
                           read_only=True)

            db_session.add(cal)
            db_session.commit()
