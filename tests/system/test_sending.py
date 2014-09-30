# -*- coding: utf-8 -*-
import pytest
from time import strftime
from conftest import timeout_loop, all_accounts
from random_words import random_words
from inbox.util.url import provider_from_address


@timeout_loop('send')
def wait_for_send(client, subject):
    thread_query = client.threads.where(subject=subject)

    threads = thread_query.all()

    if not threads:
        return False
    if provider_from_address(client.email_address) not in ['unknown', 'eas']:
        # Reconciliation doesn't seem to quite work on EAS because the
        # X-INBOX-ID header is stripped?
        assert len(threads) == 1, \
            "Warning: Number of threads for unique subject is > 1!"

    tags = [t['name'] for thread in threads for t in thread.tags]
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


@pytest.mark.parametrize("client", all_accounts)
def test_sending(client):
    # because of T478 these tests don't pass on iCloud
    if provider_from_address(client.email_address) == "icloud":
        print "Sending disabled for iCloud because of their sent behavior"
        return
    # Create a message and send it to ourselves
    subject = "%s (Self Send Test)" % strftime("%Y-%m-%d %H:%M:%S")
    draft = client.drafts.create(to=[{"email": client.email_address}],
                                 subject=subject,
                                 body=subject + "Test email.")

    body = random_words(sig=client.email_address.split('@')[0])

    draft = client.drafts.create(to=[{"email": client.email_address}],
                                 subject=subject,
                                 body=body)
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
