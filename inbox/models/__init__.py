""" Top level module for all models """

from inbox.util.misc import load_modules


from inbox.models.account import Account
from inbox.models.base import MailSyncBase, MAX_FOLDER_NAME_LENGTH
from inbox.models.block import Block, Part
from inbox.models.contact import MessageContactAssociation, Contact
from inbox.models.folder import Folder, FolderItem
from inbox.models.lens import Lens
from inbox.models.message import Message, SpoolMessage
from inbox.models.namespace import Namespace
from inbox.models.search import SearchToken, SearchSignal
from inbox.models.tag import Tag
from inbox.models.thread import Thread, DraftThread, TagItem
from inbox.models.transaction import Transaction
from inbox.models.webhook import Webhook

__all__ = ['Account', 'MailSyncBase', 'Block', 'Part',
           'MessageContactAssociation', 'Contact', 'Folder',
           'FolderItem', 'Lens', 'Message', 'SpoolMessage',
           'Namespace', 'SearchToken', 'SearchSignal',
           'Tag', 'TagItem', 'Thread', 'DraftThread', 'Transaction',
           'Webhook', 'MAX_FOLDER_NAME_LENGTH']


def register_backends():
    """
    Dynamically loads all packages contained within thread
    backends module, including those by other module install paths
    """
    import inbox.models.backends

    # Find and import
    modules = load_modules(inbox.models.backends)

    # Create mapping
    table_mod_for = {}
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER
            table_mod_for[provider] = module

    return table_mod_for
