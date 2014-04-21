"""Low-level module for managing hooks to invoke on newly received messages.
"""
from collections import defaultdict

from inbox.server.contacts.process_mail import update_contacts_from_message


class HookManager(object):
    """Manages hooks to invoke on newly received messages. A hook is a function
    which takes an account_id and a Message object, and does stuff.
    Hooks should really not modify the Message object, although this can't
    really be programmatically enforced by the HookManager."""
    def __init__(self):
        self._per_account_hooks = defaultdict(set)
        self._universal_hooks = set()

    def register_account_hook(self, account_id, hook):
        """Register a hook to operate only on messages belonging to the
        specified account."""
        self._per_account_hooks[account_id].add(hook)

    def register_universal_hook(self, hook):
        """Register a hook to operate on all messages."""
        self._universal_hooks.add(hook)

    def execute_hooks(self, account_id, message):
        """Execute all applicable hooks on the given account_id and message."""
        for func in self._per_account_hooks[account_id]:
            func(account_id, message)

        for func in self._universal_hooks:
            func(account_id, message)


default_hook_manager = HookManager()
default_hook_manager.register_universal_hook(update_contacts_from_message)


# At this point, we could read additional hooks from a directory, say.
