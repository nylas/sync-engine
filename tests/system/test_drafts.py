# -*- coding: utf-8 -*-
import time
import requests.exceptions
from base import for_all_available_providers
from conftest import TEST_MAX_DURATION_SECS, TEST_GRANULARITY_CHECK_SECS


@for_all_available_providers
def test_draft(client, data):
    # Let's create a draft, attach a file to it and delete it

    # Create the file
    fname = 'file_%d.txt' % time.time()
    filehash = {'file': (fname, 'This is a file')}
    files = client.create_files(filehash)

    start_time = time.time()
    file_id = files[0].id
    found_file = False
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        try:
            client.get_file(file_id)
        except requests.exceptions.HTTPError:
            continue

        found_file = True
        print ("test_file_creation\t%s\t%s" %
               (data["email"], time.time() - start_time))
        break

    assert found_file, ("Failed to find file in less"
                        "than {} seconds on account: {}").\
        format(TEST_MAX_DURATION_SECS, data["email"])

    # Attach the file to the draft
    subject = "Test draft from Inbox - %s" % time.strftime("%H:%M:%S")
    message = {"to": [{"email": data["email"]}],
               "body": "This is a test email, disregard this.",
               "subject": subject, "file_ids": [file_id]}

    draft = client.create_draft(message)
    draft_id = draft.id
    draft_version = draft.version

    start_time = time.time()
    found_draft = False
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        draft = client.get_draft(draft_id)
        if draft.id == draft_id:
            found_draft = True
            print ("test_draft_creation\t%s\t%f" %
                   (data["email"], time.time() - start_time))
            break

    assert found_draft, ("Failed to find draft in less"
                         "than {} seconds on account: {}").\
        format(TEST_MAX_DURATION_SECS, data["email"])

    # send the draft and check that it's been removed
    client.send_draft(draft_id, draft_version)

    start_time = time.time()
    found_draft = False
    # Not sure about the correct behaviour for this one -
    # are sent drafts kept?
    while time.time() - start_time < TEST_MAX_DURATION_SECS:
        time.sleep(TEST_GRANULARITY_CHECK_SECS)
        try:
            draft = client.get_draft(draft_id)
        except requests.exceptions.HTTPError:
            continue

        if draft.state == "sent":
            found_draft = True
            print ("test_draft_reconciliation\t%s\t%f" %
                   (data["email"], time.time() - start_time))
            break

    assert found_draft, ("Failed to send draft in less"
                         "than {} seconds on account: {}").\
        format(TEST_MAX_DURATION_SECS, data["email"])
