"""
Per-provider table modules.

A table module *must* meet the following requirement:

1. Live in the 'tables/' directory.
"""
# Allow out-of-tree table submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
from inbox.util.misc import register_backends
module_registry = register_backends(__name__, __path__)
