# -*- coding: utf-8 -*-
import pytest
import time
from conftest import timeout_loop, all_accounts
from inbox.client.errors import NotFoundError


@timeout_loop('file')
def wait_for_file(client, file_id):
    try:
        client.files.find(file_id)
        return True
    except NotFoundError:
        return False


@timeout_loop('draft')
def wait_for_draft(client, draft_id):
    try:
        return client.drafts.find(draft_id)
    except NotFoundError:
        return False


@timeout_loop('draft_removed')
def check_draft_is_removed(client, draft_id):
    try:
        client.drafts.find(draft_id)
        return False
    except NotFoundError:
        return True


@pytest.mark.parametrize("client", all_accounts)
def test_draft(client):
    # Let's create a draft, attach a file to it and delete it

    # Create the file
    myfile = client.files.create()
    myfile.filename = 'file_%d.txt' % time.time()
    myfile.data = 'This is a file'
    myfile.save()
    wait_for_file(client, myfile.id)

    # And the draft
    mydraft = client.drafts.create()
    mydraft.to = [{'email': client.email_address}]
    mydraft.subject = "Test draft from Inbox - %s" % time.strftime("%H:%M:%S")
    mydraft.body = "This is a test email, disregard this."
    mydraft.attach(myfile)
    mydraft.save()
    wait_for_draft(client, mydraft.id)
    mydraft.send()

    # Not sure about the correct behaviour for this one -
    # are sent drafts kept?
    # check_draft_is_removed(client, mydraft.id)


if __name__ == '__main__':
    pytest.main([__file__])
