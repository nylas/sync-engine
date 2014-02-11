""" Namespace-specific functions.

All functions in this file should take `namespace_id` as their first
argument and make sure to limit the action based on it!
"""

from .tables import Thread, FolderItem

def threads_for_folder(namespace_id, session, folder_name):
    """ NOTE: Does not work for shared folders. """
    return session.query(Thread).join(FolderItem).filter(
            Thread.namespace_id==namespace_id,
            FolderItem.folder_name==folder_name)

def archive_thread(namespace_id, session, thread_id):
    """ Archive thread in the local datastore (*not* the account backend).

    (Removes it from the 'inbox' and puts it in the 'archive' equivalent.)
    """
    item = session.query(FolderItem).join(Thread).filter(
            Thread.id==namespace_id, FolderItem.thread_id==thread_id,
            FolderItem.folder_name=='inbox').one()
    session.delete(item)
    session.commit()
    # - TODO once we support non-Gmail backends, make sure thread_id has a
    # FolderItem for the account's archive folder (we can ignore this step
    # for now)

def move_thread(namespace_id, session, thread_id, from_folder, to_folder):
    """ Move thread in the local datastore (*not* the account backend). """
    listing = session.query(FolderItem).join(Thread).filter(
            Thread.namespace_id==namespace_id,
            FolderItem.thread_id==thread_id,
            FolderItem.folder_name==from_folder).one()
    listing.folder_name = to_folder
    session.commit()

def copy_thread(namespace_id, session, thread_id, from_folder, to_folder):
    """ Copy thread in the local datastore (*not* the account backend). """
    existing = session.query(FolderItem).join(Thread).filter(
            Thread.namespace_id==namespace_id,
            FolderItem.thread_id==thread_id,
            FolderItem.folder_name==from_folder).one()
    new = FolderItem(thread=existing.thread, folder_name=to_folder)
    session.add(new)
    session.commit()

def delete_thread(namespace_id, session, thread_id, folder_name):
    """ Delete thread in the local datastore (*not* the account backend). """
    item = session.query(FolderItem).join(Thread).filter(
            Thread.id==namespace_id, FolderItem.thread_id==thread_id,
            FolderItem.folder_name==folder_name).one()
    session.delete(item)
    session.commit()
