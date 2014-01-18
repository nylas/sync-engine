""" Code for propagating Inbox datastore changes to the account backend. """

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

def get_delete_fn(imapaccount):
    return mod_for[imapaccount.provider].delete
