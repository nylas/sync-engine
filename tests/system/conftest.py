# This file contains pytest fixtures as well as some config

API_BASE = "http://localhost:5555"
TEST_MAX_DURATION_SECS = 360
TEST_GRANULARITY_CHECK_SECS = 0.1

import pytest
from time import time, sleep
from client import InboxTestClient
from inbox.auth import handler_from_email
from inbox.util.url import provider_from_address
from inbox.models.session import session_scope
from google_auth_helper import google_auth
from outlook_auth_helper import outlook_auth
from inbox.auth.gmail import create_auth_account as create_gmail_account
from inbox.auth.outlook import create_auth_account as create_outlook_account


# we don't want to commit passwords to the repo.
# load them from an external json file.
try:
    from accounts import credentials as raw_credentials
    credentials = [(c['user'], c['password']) for c in raw_credentials]
    all_accounts = [InboxTestClient(email) for email, _ in credentials]
except ImportError:
    print ("Error: test accounts file not found. "
           "You need to create accounts.py\n"
           "File format: credentials = [{'user': 'bill@example.com', "
           "'password': 'VerySecret'}]")
    raise


def timeout_loop(name):
    def wrap(f):
        def wrapped_f(*args, **kwargs):
            client = args[0]
            print "Waiting for: {}...".format(name)
            success = False
            start_time = time()
            while time() - start_time < TEST_MAX_DURATION_SECS:
                if f(*args, **kwargs):
                    success = True
                    break
                sleep(TEST_GRANULARITY_CHECK_SECS)

            assert success, ("Failed to {} in less than {}s on {}"
                             .format(name, TEST_MAX_DURATION_SECS,
                                     client.email_address))

            format_test_result(name, client.provider,
                               client.email_address, start_time)
            return True
        return wrapped_f
    return wrap


def format_test_result(function_name, provider, email, start_time):
    print "%s\t%s\t%s\t%f" % (function_name, provider,
                              email, time() - start_time)


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
