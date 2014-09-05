# -*- coding: utf-8 -*-
import pytest
from time import strftime
from base import for_all_available_providers, timeout_loop


@timeout_loop('send')
def wait_for_send(client, subject):
    thread_query = client.threads.where(subject=subject)
    if len(thread_query.all()) != 2:
        return False
    tags = [t['name'] for thread in thread_query for t in thread.tags]
    return True if ("sent" in tags and "inbox" in tags) else False


@timeout_loop('archive')
def wait_for_archive(client, thread_id):
    thread = client.threads.find(thread_id)
    tags = [tag["name"] for tag in thread.tags]
    return True if ("archive" in tags and "inbox" not in tags) else False


@timeout_loop('trash')
def wait_for_trash(client, thread_id):
    thread = client.threads.find(thread_id)
    tags = [tag['name'] for tag in thread.tags]
    return True if ("trash" in tags and "archive" not in tags) else False


@for_all_available_providers
def test_sending(client):
    # Create a message and send it to ourselves
    subject = "%s (Self Send Test)" % strftime("%Y-%m-%d %H:%M:%S")
    draft = client.drafts.create(to=[{"email": client.email_address}],
                                 subject=subject,
                                 body="Test email.")
    draft.send()
    wait_for_send(client, subject)

    # Archive the message
    thread = client.threads.where(subject=subject, tag='inbox').first()
    thread.archive()
    wait_for_archive(client, thread.id)

    # Trash the message (Raises notimplementederror)
    # remove False guard when working
    if False:
        client.threads.first().trash()
        wait_for_trash(client, thread.id)


if __name__ == '__main__':
    pytest.main([__file__])
