# -*- coding: utf-8 -*-
# base.py: Basic functions for end-to-end testing.
#
# Here's how testing works. The tests for a specific REST resource
# are in test_resource.py. Each file contains one or more test class
# which inherits E2ETest, and an additional mixin class.
#
# For instance, if you want to define a test which will run against
# a gmail account, you test class will inherit E2ETest and GmailMixin.
import time
from inbox.auth import handler_from_email
from inbox.util.url import provider_from_address
from inbox.models.session import session_scope
from conftest import (passwords, TEST_MAX_DURATION_SECS,
                      TEST_GRANULARITY_CHECK_SECS)
from google_auth_helper import google_auth
from outlook_auth_helper import outlook_auth
from inbox.auth.gmail import create_auth_account as create_gmail_account
from inbox.auth.outlook import create_auth_account as create_outlook_account
from client import APIClient


def for_all_available_providers(fn):
    """Run a test on all providers defined in accounts.py. This function
    handles account setup and teardown."""
    def f():
        for email, password in passwords:
            with session_scope() as db_session:
                create_account(db_session, email, password)

            client = None
            ns = None
            start_time = time.time()
            while time.time() - start_time < TEST_MAX_DURATION_SECS:
                time.sleep(TEST_GRANULARITY_CHECK_SECS)
                client, ns = APIClient.from_email(email)
                if client is not None:
                    break

            assert client, ("Creating account from password file"
                            " should have been faster")
            format_test_result("namespace_creation_time", ns["provider"],
                               email, start_time)

            # wait a little time for the sync to start. It's necessary
            # because a lot of tests rely on stuff setup at the beginning
            # of the sync (for example, a folder hierarchy).
            start_time = time.time()
            sync_started = False
            while time.time() - start_time < TEST_MAX_DURATION_SECS:
                msgs = client.get_messages()
                if len(msgs) > 0:
                    sync_started = True
                    break
                time.sleep(TEST_GRANULARITY_CHECK_SECS)

            assert sync_started, ("The initial sync should have started")

            data = {"email": ns["email_address"], "provider": ns["provider"]}
            start_time = time.time()
            fn(client, data)
            format_test_result(fn.__name__, ns["provider"],
                               ns["email_address"],
                               start_time)

            with session_scope() as db_session:
                # delete account
                pass

    return f


def create_account(db_session, email, password):
    provider = provider_from_address(email)
    auth_handler = handler_from_email(email)
    # Special-case Gmail and Outlook, because we need to provide an oauth token
    # and not merely a password.
    if provider == 'gmail':
        token = google_auth(email, password)
        account = create_gmail_account(db_session, email, token, False)
    elif provider == 'outlook':
        token = outlook_auth(email, password)
        account = create_outlook_account(db_session, email, token, False)
    else:
        response = {"email": email, "password": password}
        account = auth_handler.create_account(db_session, email, response)

    auth_handler.verify_account(account)

    db_session.add(account)
    db_session.commit()
    return account


def format_test_result(function_name, provider, email, start_time):
    print "%s\t%s\t%s\t%f" % (function_name, provider,
                              email, time.time() - start_time)
