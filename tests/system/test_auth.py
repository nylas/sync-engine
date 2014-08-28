import pytest
import time
from client import APIClient
from base import create_account
from inbox.models.session import session_scope
from conftest import (TEST_MAX_DURATION_SECS, TEST_GRANULARITY_CHECK_SECS,
                      passwords)


@pytest.mark.parametrize('email,password', passwords)
def test_password_auth(email, password):
    with session_scope() as db_session:
        create_account(db_session, email, password)

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
        # remove_account(db_session, email)
        pass
