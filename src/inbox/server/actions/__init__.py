""" Code for propagating Inbox datastore changes to the account backend.

Syncback actions don't update anything in the local datastore; the Inbox
datastore is updated asynchronously (see namespace.py) and bookkeeping about
the account backend state is updated when the changes show up in the mail sync
engine.

Dealing with write actions separately from read syncing allows us more
flexibility in responsiveness/latency on data propagation, and also makes us
unable to royally mess up a sync and e.g. accidentally delete a bunch of
messages on the account backend because our local datastore is messed up.

This read/write separation also allows us to easily disable syncback for
testing.

The main problem the separation presents is the fact that the read syncing
needs to deal with the fact that the local datastore may have new changes to
it that are not yet reflected in the account backend. In practice, this is
not really a problem because of the limited ways mail messages can change.
(For more details, see individual account backend submodules.)

ACTIONS MUST BE IDEMPOTENT! We are going to have task workers guarantee
at-least-once semantics.
"""
from redis import Redis
from rq import Queue, Connection

from . import gmail

from inbox.server.util.concurrency import GeventWorker
from inbox.server.config import config

mod_for = {'Gmail': gmail}

def get_queue():
    # The queue label is set via config to allow multiple distinct Inbox
    # instances to hit the same Redis server without interfering with each
    # other.
    return Queue(config.get('ACTION_QUEUE_LABEL', None), connection=Redis())

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
