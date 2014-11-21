# This file contains pytest fixtures as well as some config
import os
API_BASE = "http://%s:%s" % (os.getenv("API_PORT_5555_TCP_ADDR","localhost"),os.getenv("API_PORT_5555_TCP_PORT","5555"))
TEST_MAX_DURATION_SECS = 360
TEST_GRANULARITY_CHECK_SECS = 0.1

from time import time, sleep
from client import InboxTestClient
from inbox.util.url import provider_from_address
from google_auth_helper import google_auth
from outlook_auth_helper import outlook_auth
from inbox.auth import handler_from_provider


# we don't want to commit passwords to the repo.
# load them from an external json file.
try:
    from accounts import credentials as raw_credentials
    credentials = [(c['user'], c['password']) for c in raw_credentials]
    all_accounts = [InboxTestClient(email, API_BASE) for email, _ in credentials]
    gmail_accounts = [InboxTestClient(email, API_BASE)
                      for email, password in credentials
                          if "gmail.com" in email]

    calendar_providers = ["gmail.com", "onmicrosoft.com"]
    calendar_accounts = [InboxTestClient(email, API_BASE)
                         for email, password in credentials
                            if any(domain in email for domain in calendar_providers)]

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
    auth_handler = handler_from_provider(provider)
    # Special-case Gmail and Outlook, because we need to provide an oauth token
    # and not merely a password.
    response = {'email': email}
    if provider == 'gmail':
        code = google_auth(email, password)
        response = auth_handler._get_authenticated_user(code)
    elif provider == 'outlook':
        code = outlook_auth(email, password)
        response = auth_handler._get_authenticated_user(code)
    else:
        response = {"email": email, "password": password}

    account = auth_handler.create_account(db_session, email, response)
    auth_handler.verify_account(account)

    db_session.add(account)
    db_session.commit()
    return account
