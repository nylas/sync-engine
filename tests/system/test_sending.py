# -*- coding: utf-8 -*-
import pytest
import time
from base import for_all_available_providers
from conftest import TEST_MAX_DURATION_SECS, TEST_GRANULARITY_CHECK_SECS


@for_all_available_providers
def test_sending(client, data):
    # Let's send a message to ourselves and check that it arrived.
    subject = "Test email from Inbox - %s" % time.strftime("%H:%M:%S")
    message = {"to": [{"email": data["email"]}],
               "body": "This is a test email, disregard this.",
               "subject": subject}

    send_req = client.send_message(message)
    assert send_req.status_code == 200

    start_time = time.time()
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        threads = client.get_threads(subject=subject)
        if not len(threads) == 2:
            continue

        tags = [t["name"] for thread in threads for t in thread.tags]
        if ("sent" in tags and "inbox" in tags):
            return

    assert False, ("Failed to self send an email in less"
                   "than {} seconds on account: {}").format(
        TEST_MAX_DURATION_SECS,
        data["email"])


if __name__ == '__main__':
    pytest.main([__file__])
