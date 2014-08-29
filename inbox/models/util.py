from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.models.message import Message
from inbox.models.thread import Thread
from inbox.models.folder import Folder, FolderItem

from inbox.util.file import Lock


from inbox.log import get_logger
log = get_logger()


def reconcile_message(db_session, inbox_uid, new_msg):
    """
    Identify a `Sent Mail` (or corresponding) message synced from the
    remote backend as one we sent and reconcile it with the message we
    created and stored in the local data store at the time of sending.

    Notes
    -----
    Our current reconciliation strategy is to keep both messages i.e.
    the one we sent and the one we synced.

    """
    try:
        message = db_session.query(Message).filter(
            Message.version == inbox_uid).one()
        assert message.is_created
        message.resolved_message = new_msg
        return message

    # Don't raise here because message is an Inbox created message but
    # not by this client i.e. the Inbox created version is not present in the
    # local data store.
    except NoResultFound:
        log.warning('NoResultFound for this message, even though '
                    'it has the inbox-sent header: {0}'.format(inbox_uid))

    except MultipleResultsFound:
        log.error('MultipleResultsFound when reconciling message with '
                  'inbox-sent header: {0}'.format(inbox_uid))
        raise

# Namespace Utils


def _db_write_lockfile_name(account_id):
    return "/var/lock/inbox_datastore/{0}.lock".format(account_id)


def db_write_lock(namespace_id):
    """ Protect updating this namespace's Inbox datastore data.

    Note that you should also use this to wrap any code that _figures
    out_ what to update the datastore with, because outside the lock
    you can't guarantee no one is updating the data behind your back.
    """
    return Lock(_db_write_lockfile_name(namespace_id), block=True)


def threads_for_folder(namespace_id, session, folder_name):
    """ NOTE: Does not work for shared folders. """
    return session.query(Thread).join(FolderItem).join(Folder).filter(
        Thread.namespace_id == namespace_id,
        Folder.name == folder_name)
