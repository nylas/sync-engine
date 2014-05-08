""" Gmail-specific operations for modifying mail data. """

from inbox.server.actions.gmail.local import (local_archive, local_move,
                                              local_copy, local_delete)
from inbox.server.actions.gmail.remote import (remote_archive, remote_move,
                                               remote_copy, remote_delete,
                                               uidvalidity_cb)

PROVIDER = 'Gmail'
