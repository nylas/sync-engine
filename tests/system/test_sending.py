# -*- coding: utf-8 -*-
import pytest
import time
from base import for_all_available_providers, format_test_result
from conftest import TEST_MAX_DURATION_SECS, TEST_GRANULARITY_CHECK_SECS


@for_all_available_providers
def test_sending(client, data):
    # Let's send a message to ourselves and check that it arrived.

    subject = "Test email from Inbox - %s" % time.strftime("%H:%M:%S")
    message = {"to": [{"email": data["email"]}],
               "body": "This is a test email, disregard this.",
               "subject": subject}

    client.send_message(message)

    start_time = time.time()
    found_email = False
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        threads = client.get_threads(subject=subject)
        if not len(threads) == 2:
            continue

        tags = [t["name"] for thread in threads for t in thread.tags]
        if ("sent" in tags and "inbox" in tags):
            format_test_result("self_send_test", data["provider"],
                               data["email"], start_time)
            found_email = True
            break

    assert found_email, ("Failed to self send an email in less"
                         "than {} seconds on account: {}").format(
        TEST_MAX_DURATION_SECS,
        data["email"])

    # Now let's archive the email.

    threads = client.get_threads(subject=subject)
    # Note: this uses python's implicit scoping
    for thread in threads:
        if "inbox" in thread.tags:
            break

    client.update_tags(thread.id, {"add_tags": ["archive"],
                                   "remove_tags": ["inbox"]})

    updated_tags = False
    start_time = time.time()
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        thr = client.get_thread(thread.id)

        tags = [tag["name"] for tag in thr.tags]
        if "archive" in tags and "inbox" not in tags:
            format_test_result("archive_test", data["provider"],
                               data["email"], start_time)
            updated_tags = True
            break

    assert updated_tags, ("Failed to archive an email in less"
                          "than {} seconds on account: {}").format(
        TEST_MAX_DURATION_SECS,
        data["email"])

    client.update_tags(thread.id, {"add_tags": ["trash"],
                                   "remove_tags": ["archive"]})

    updated_tags = False
    start_time = time.time()
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        thr = client.get_thread(thread.id)

        if "trash" in thr.tags and "archive" not in thr.tags:
            format_test_result("move_to_trash_test", data["provider"],
                               data["email"], start_time)
            updated_tags = True
            break

    assert updated_tags, ("Failed to move an email to trash in less"
                          "than {} seconds on account: {}").format(
        TEST_MAX_DURATION_SECS,
        data["email"])


if __name__ == '__main__':
    pytest.main([__file__])
