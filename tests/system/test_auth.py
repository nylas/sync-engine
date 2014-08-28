import pytest
import time
from client import APIClient
from base import create_account
from inbox.auth.generic import delete_account
from inbox.auth import handler_from_email
from inbox.models.session import session_scope
from conftest import (TEST_MAX_DURATION_SECS, TEST_GRANULARITY_CHECK_SECS,
                      passwords)


@pytest.mark.parametrize('email,password', passwords)
def test_password_auth(email, password):
    with session_scope() as db_session:
        auth_handler = handler_from_email(email)
        account = create_account(db_session, email, password)
        if auth_handler.verify_account(account):
            db_session.add(account)
            db_session.commit()

    start_time = time.time()

    # Check that the account exists
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        client = APIClient.from_email(email)[0]
        if client is not None:
            break
        time.sleep(TEST_GRANULARITY_CHECK_SECS)

    if client is None:
        assert False, "Account namespace should have been created"

    # Now, compute how much time it takes to start syncing the account
    start_time = time.time()
    got_messages = False
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        messages = client.get_messages()
        if len(messages) != 0:
            got_messages = True
            break
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
    assert got_messages, "Messages should have been found"

    print "test_password_auth %s %f" % (email, time.time() - start_time)

    # remove the account
    with session_scope() as db_session:
        delete_account(db_session, email)
