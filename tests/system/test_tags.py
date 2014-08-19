# -*- coding: utf-8 -*-
import pytest
import random
import time
import datetime
import requests.exceptions
from base import for_all_available_providers
from conftest import TEST_MAX_DURATION_SECS, TEST_GRANULARITY_CHECK_SECS


@for_all_available_providers
def test_read_status(client, data):
    # toggle a thread's read status
    messages = client.get_messages()
    msg = random.choice(messages)
    unread = msg.unread
    thread_id = msg.thread

    if unread:
        client.update_tags(thread_id, {"add_tags": ["read"]})
    else:
        client.update_tags(thread_id, {"add_tags": ["unread"]})

    start_time = time.time()
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        try:
            thread = client.get_thread(thread_id)
        except requests.exceptions.HTTPError:
            continue

        tags = [tag["name"] for tag in thread.tags]
        if unread:
            if "read" in tags:
                print ("test_change_read_status %s %s" %
                       (data["email"], time.time() - start_time))
                return
        else:
            if "unread" in tags:
                print ("test_change_read_status %s %s" %
                       (data["email"], time.time() - start_time))
                return
    assert False, ("Failed to change read status in less"
                   "than {} seconds on account: {}").format(
        TEST_MAX_DURATION_SECS,
        data["email"])


@for_all_available_providers
def test_custom_tag(client, data):
    threads = client.get_threads()
    thread = random.choice(threads)
    tagname = "custom-tag" + datetime.datetime.now().strftime("%s.%f")
    client.create_tag(tagname)
    client.update_tags(thread["id"], {"add_tags": [tagname]})

    start_time = time.time()
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        try:
            thread = client.get_thread(thread["id"])
        except requests.exceptions.HTTPError:
            continue

        tags = [tag["name"] for tag in thread.tags]
        if tagname in tags:
            return

    assert False, ("Failed to apply custom tag in less"
                   "than {} seconds on account: {}").format(
        TEST_MAX_DURATION_SECS,
        data["email"])

if __name__ == '__main__':
    pytest.main([__file__])
