# -*- coding: utf-8 -*-
import pytest
import random
from datetime import datetime
from conftest import timeout_loop, all_accounts


@timeout_loop('tag_add')
def wait_for_tag(client, thread_id, tagname):
    thread = client.threads.find(thread_id)
    tags = [tag['name'] for tag in thread.tags]
    return True if tagname in tags else False


@timeout_loop('tag_remove')
def wait_for_tag_removal(client, thread_id, tagname):
    thread = client.threads.find(thread_id)
    tags = [tag['name'] for tag in thread.tags]
    return True if tagname not in tags else False


@pytest.mark.parametrize("client", all_accounts)
def test_read_status(client):
    # toggle a thread's read status
    msg = random.choice(client.messages.all())
    unread = msg.unread
    thread = client.threads.find(msg.thread_id)

    if unread:
        thread.mark_as_read()
        wait_for_tag_removal(client, thread.id, "unread")
    else:
        thread.add_tags(["unread"])
        wait_for_tag(client, thread.id, "unread")


@pytest.mark.parametrize("client", all_accounts)
def test_custom_tag(client):
    thread = random.choice(client.threads.all())
    tagname = "custom-tag" + datetime.now().strftime("%s.%f")

    t = client.tags.create(name=tagname)
    t.save()

    thread.add_tags([tagname])
    wait_for_tag(client, thread.id, tagname)
    thread = client.threads.find(thread.id)

    thread.remove_tags([tagname])
    wait_for_tag_removal(client, thread.id, tagname)

    client.tags.delete(t.id)


@pytest.mark.parametrize("client", all_accounts)
def test_archive_tag(client):
    thread = random.choice(client.threads.all())
    thread.add_tags(["archive"])
    wait_for_tag(client, thread.id, "archive")
    thread = client.threads.find(thread.id)
    tags = [tag['name'] for tag in thread.tags]
    assert 'inbox' not in tags, ("Adding the archive tag should"
                                 "remove the inbox tag")

    # Remove the archive tag and check it's now back in
    # Inbox.
    thread.remove_tags(["archive"])
    wait_for_tag_removal(client, thread.id, "archive")

    thread = client.threads.find(thread.id)
    tags = [tag['name'] for tag in thread.tags]

    assert 'archive' not in tags and 'inbox' in tags, ("removing archive tag "
                                                       "should add inbox tag")


@pytest.mark.xfail
@pytest.mark.parametrize("client", all_accounts)
def test_spam_tag(client):
    # mark a thread as spam, trash it and check the
    # spam tag is kept.
    thread = random.choice(client.threads.all())
    thread.add_tags(["spam"])
    wait_for_tag(client, thread.id, "spam")

    thread.add_tags(["trash"])
    wait_for_tag(client, thread.id, "trash")

    thread = client.threads.find(thread.id)
    tags = [tag['name'] for tag in thread.tags]
    assert 'spam' in tags and 'trash' in tags, ("trashing a file should"
                                                "preserve the spam tag")

    # remove both. Check that the file is back in inbox.
    thread.remove_tags(["spam", "trash"])
    wait_for_tag_removal(client, thread.id, "spam")
    wait_for_tag_removal(client, thread.id, "trash")
    thread = client.threads.find(thread.id)
    tags = [tag['name'] for tag in thread.tags]
    assert 'inbox' in tags, "Thread should be back in Inbox"


if __name__ == '__main__':
    pytest.main([__file__])
