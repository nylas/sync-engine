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
