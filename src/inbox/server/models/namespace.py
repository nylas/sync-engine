""" Namespace-specific functions. """

from .tables import Thread, FolderItem

def threads_for_folder(namespace_id, session, folder_name):
    """ NOTE: Does not work for shared folders. """
    return session.query(Thread).join(FolderItem).filter(
            Thread.namespace_id==namespace_id,
            FolderItem.folder_name==folder_name)
