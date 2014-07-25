"""
Per-provider backend modules for sending mail.

A backend module *must* meet the following requirements:

1. Specify the provider it implements as the module-level `PROVIDER` variable.
For example, 'gmail', 'eas' etc.

2. Specify the name of the sendmail class as the module-level
`SENDMAIL_CLS` variable.

"""
# Allow out-of-tree backend submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

from inbox.util.misc import register_backends

module_registry = register_backends(__name__, __path__)

from inbox.sendmail.base import (create_draft, update_draft, delete_draft,
                                 get_draft)

__all__ = ['create_draft', 'update_draft', 'delete_draft',
           'get_draft']
