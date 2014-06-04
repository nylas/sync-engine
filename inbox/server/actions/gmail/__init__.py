""" Gmail-specific operations for modifying mail data. """
from inbox.server.actions.gmail.local import (
    local_archive, local_move, local_copy, local_delete,
    set_local_unread, local_save_draft)
from inbox.server.actions.gmail.remote import (
    remote_archive, remote_move, remote_copy, remote_delete, uidvalidity_cb,
    set_remote_unread, remote_save_draft)

__all__ = ['local_archive', 'local_move', 'local_copy', 'local_delete',
           'set_local_unread', 'remote_archive', 'remote_move', 'remote_copy',
           'remote_delete', 'uidvalidity_cb', 'set_remote_unread',
           'local_save_draft', 'remote_save_draft']

PROVIDER = 'Gmail'
