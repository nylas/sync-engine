# -*- coding: utf-8 -*-
import pytest
from time import strftime
from conftest import timeout_loop, all_accounts
from random_words import random_words
from inbox.util.url import provider_from_address
import json


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

    # Trash the message
    # Remove guard when working
    if False:
        client.threads.first().trash()
        wait_for_trash(client, thread.id)


# TODO: do these tests even get run??
@pytest.mark.parametrize("client", all_accounts)
def test_multi_sending(client):
    # Create a message and send it to ourselves, with a different body
    subject = "%s (Self Multi Send Test)" % strftime("%Y-%m-%d %H:%M:%S")
    sent_body = subject + "Test email."
    draft = client.drafts.create(to=[{"email": client.email_address}],
                                 subject=subject,
                                 body=sent_body)
    recv_body = subject + "Different body"

    resp = client.session.post('{}/send-multiple'.format(client.api_server))
    assert resp.status_code == 200

    resp = client.session.post('{}/send-multiple/{}'.format(client.api_server,
                                                            draft.id),
                               data=json.dumps({"body": recv_body,
                                                "send_to": [
                                                    {"email":
                                                        client.email_address}
                                                ]}))
    assert resp.status_code == 200
    wait_for_send(client, subject)

    resp = client.session.delete('{}/send-multiple/{}'
                                 .format(client.api_server, draft.id))
    assert resp.status_code == 200
    wait_for_send(client, subject)

    # Check that there are two messages, one sent and one recieved, with
    # different bodies.
    thread = client.threads.where(subject=subject, tag='inbox').first()
    assert len(thread.messages) == 2
    assert thread.messages[0].body == recv_body
    assert thread.messages[1].body == sent_body

    # Archive the thread
    thread = client.threads.where(subject=subject, tag='inbox').first()
    thread.archive()
    wait_for_archive(client, thread.id)

    # Trash the message
    # Remove guard when working
    if False:
        client.threads.first().trash()
        wait_for_trash(client, thread.id)


if __name__ == '__main__':
    pytest.main([__file__])
