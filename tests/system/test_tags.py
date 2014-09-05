# -*- coding: utf-8 -*-
import pytest
import random
from datetime import datetime
from base import for_all_available_providers, timeout_loop


@timeout_loop('tag_add')
def wait_for_tag(client, thread_id, tagname):
    thread = client.threads.find(thread_id)
    tags = [tag['name'] for tag in thread.tags]
    return True if tagname in tags else False


@timeout_loop('tag_remove')
def wait_for_tag_removal(client, thread_id, tagname):
    return not wait_for_tag(client, thread_id, tagname)


@for_all_available_providers
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


@for_all_available_providers
def test_custom_tag(client):
    thread = random.choice(client.threads.all())
    tagname = "custom-tag" + datetime.now().strftime("%s.%f")

    t = client.tags.create(name=tagname)
    t.save()

    thread.add_tags([tagname])
    wait_for_tag(client, thread.id, tagname)

    thread.remove_tags([tagname])
    wait_for_tag_removal(client, thread.id, tagname)

    client.tags.delete(t.id)


if __name__ == '__main__':
    pytest.main([__file__])
