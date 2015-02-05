"""
An action module *must* meet the following requirement:

1. Specify the provider it implements as the module-level PROVIDER variable.
For example, 'gmail', 'imap', 'eas', 'yahoo' etc.

2. Live in the 'inbox.actions.backends' module tree.

"""
# Allow out-of-tree action submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
from inbox.util.misc import register_backends
module_registry = register_backends(__name__, __path__)
