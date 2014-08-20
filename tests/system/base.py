# -*- coding: utf-8 -*-
# base.py: Basic functions for end-to-end testing.
#
# Here's how testing works. The tests for a specific REST resource
# are in test_resource.py. Each file contains one or more test class
# which inherits E2ETest, and an additional mixin class.
#
# For instance, if you want to define a test which will run against
# a gmail account, you test class will inherit E2ETest and GmailMixin.
import client
import time
from inbox.auth import handler_from_email
from inbox.util.url import provider_from_address
from google_auth_helper import google_auth
from outlook_auth_helper import outlook_auth
from inbox.auth.gmail import create_auth_account as create_gmail_account
from inbox.auth.outlook import create_auth_account as create_outlook_account


def for_all_available_providers(fn):
    """Run a test on all supported providers. Also output timing data"""
    namespaces = client.APIClient.namespaces()

    def f():
        for ns in namespaces:
            cl = client.APIClient(ns["namespace"])
            data = {"email": ns["email_address"]}
            start_time = time.time()
            fn(cl, data)
            print "%s\t%s\t%f" % (fn.__name__, ns["provider"],
                                  time.time() - start_time)
    return f


def pick(l, predicate):
    for el in l:
        if predicate(el):
            return el


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
