""" Code for propagating Inbox datastore changes to the account backend.

Dealing with write actions separately from read syncing allows us more
flexibility in responsiveness/latency on data propagation, and also makes us
much less likely to royally mess up a sync and e.g. accidentally delete a bunch
of messages on the account backend because our local datastore is messed up.
"""

from redis import Redis
from rq import Queue

from . import gmail

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
