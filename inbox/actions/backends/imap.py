""" Operations for syncing back local datastore changes to IMAP servers.

We could guarantee correctness with a full bidirectional sync by using a
conservative algorithm like OfflineIMAP's
(http://offlineimap.org/howitworks.html), but doing so wouldn't take advantage
of newer IMAP extensions like CONDSTORE that make us have to do much less
comparison and bookkeeping work. We also want to sync mail to us in full
daemon mode.

We don't get any notion of "transactions" from the remote with IMAP. Here are
the possible cases for IMAP message changes:

* new
  - This message is either new-new and needs to be synced to us, or it's a
    "sent" or "draft" message and we need to check whether or not we have it,
    since we may have already saved a local copy. If we do already have it,
    we need to make a new ImapUid for it and associate the Message object with
    its ImapUid.
* changed
  - Update our flags or do nothing if the message isn't present locally. (NOTE:
    this could mean the message has been moved locally, in which case we will
    LOSE the flag change. We can fix this case in an eventually consistent
    manner by sanchecking flags on all messages in an account once a day or
    so.)
* delete
  - We always figure this out by comparing message lists against the local
    repo. Since we're using the mailsync-specific ImapUid objects for
    comparison, we automatically exclude Inbox-local sent and draft messages
    from this calculation.

We don't currently handle these operations on the special folders 'junk',
'trash', 'sent', 'flagged'.
"""
from inbox.crispin import writable_connection_pool, retry_crispin
from inbox.mailsync.backends.imap.generic import uidvalidity_cb


# Because we wrap with retry_crispin here, IMAP syncback actions can *in
# theory* be retried up to 5 * ACTION_MAX_NR_OF_RETRIES times in total. In
# practice, failures handled by retry_crispin should generally resolve
# immediately after getting a new connection.
@retry_crispin
def syncback_action(fn, account, folder_name, db_session):
    """ `folder_name` is a provider folder name, not a local tag

    `folder_name` is the folder which is selected before `fn` is called.

    """
    assert folder_name, "folder '{}' is not selectable".format(folder_name)

    # NOTE: This starts a *new* IMAP session every time---we will want
    # to optimize this at some point. But for now, it's most correct.
    with writable_connection_pool(account.id).get() as crispin_client:
            crispin_client.select_folder(folder_name, uidvalidity_cb)
            fn(account, db_session, crispin_client)
