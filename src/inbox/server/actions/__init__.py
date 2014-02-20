""" Code for propagating Inbox datastore changes to the account backend.

Dealing with write actions separately from read syncing allows us more
flexibility in responsiveness/latency on data propagation, and also makes us
unable to royally mess up a sync and e.g. accidentally delete a bunch of
messages on the account backend because our local datastore is messed up. We
could guarantee correctness with a full bidirectional sync by using a
conservative algorithm like OfflineIMAP's
(http://offlineimap.org/howitworks.html), but doing so wouldn't take advantage
of newer IMAP extensions like CONDSTORE that make us have to do much less
comparison and bookkeeping work, and we can more easily optimize the remaining
options.

The main problem the separation presents is the fact that the read syncing
needs to deal with the fact that the local datastore may have new changes to
it, and we don't get any notion of "transactions" from the remote, at least for
IMAP backends. Here are the possible cases for IMAP message changes with this
in mind:

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
    repo. Since we're using the mailsync-specific ImapUid objects for comparison,
    we automatically exclude Inbox-local sent and draft messages from this
    calculation.

This read/write separation also allows us to easily disable syncback for
testing.
"""

from redis import Redis
from rq import Queue, Connection

from . import gmail

from inbox.server.util.concurrency import GeventWorker

mod_for = {'Gmail': gmail}

def get_queue():
    return Queue('action', connection=Redis())

def get_archive_fn(imapaccount):
    return mod_for[imapaccount.provider].archive

def get_move_fn(imapaccount):
    return mod_for[imapaccount.provider].move

def get_copy_fn(imapaccount):
    return mod_for[imapaccount.provider].copy

def get_delete_fn(imapaccount):
    return mod_for[imapaccount.provider].delete

# Later we're going to want to consider a pooling mechanism. We may want to
# split actions queues by remote host, for example, and have workers for a
# given host share a connection pool.
def rqworker(burst=False):
    """ Runs forever.

    More details on how workers work at: http://python-rq.org/docs/workers/
    """
    with Connection():
        q = get_queue()

        w = GeventWorker([q])
        w.work(burst=burst)
