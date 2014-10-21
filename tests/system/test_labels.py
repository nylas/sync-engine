# gmail-specific label handling tests.
import pytest
import random
from datetime import datetime

from inbox.crispin import writable_connection_pool
from inbox.models.session import session_scope
from inbox.models import Account
from inbox.mailsync.backends.imap.generic import uidvalidity_cb

from conftest import gmail_accounts, timeout_loop


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


@pytest.mark.parametrize("client", gmail_accounts)
def test_gmail_labels(client):
    # test case: create a label on the gmail account
    # apply it to a thread. Check that it gets picked up.
    # Remove it. Check that it gets picked up.
    thread = random.choice(client.threads.all())

    account = None
    with session_scope() as db_session:
        account = db_session.query(Account).filter_by(
            email_address=client.email_address).one()

        with writable_connection_pool(account.id, pool_size=1).get() as crispin_client:
            labelname = "custom-label" + datetime.now().strftime("%s.%f")
            print "Label: %s" % labelname

            folder_name = crispin_client.folder_names()['all']
            crispin_client.select_folder(folder_name, uidvalidity_cb)

            print "Subject : %s" % thread.subject
            uids = crispin_client.search_uids(['SUBJECT "%s"' % thread.subject])
            g_thrid = crispin_client.g_metadata(uids).items()[0][1].thrid

            crispin_client.add_label(g_thrid, labelname)
            wait_for_tag(client, thread.id, labelname)

            draft = client.drafts.create(to=[{'name': 'Inbox SelfSend',
                                         'email': client.email_address}],
                                         body="Blah, replying to message",
                                         subject=thread.subject)
            draft.send()
            wait_for_tag(client, thread.id, labelname)

            crispin_client.remove_label(g_thrid, labelname)
            wait_for_tag_removal(client, thread.id, labelname)


if __name__ == '__main__':
    pytest.main([__file__])
