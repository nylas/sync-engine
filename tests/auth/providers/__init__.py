# Allow out-of-tree auth submodules.
from pkgutil import extend_path
from inbox.util.misc import register_backends
__path__ = extend_path(__path__, __name__)
module_registry = register_backends(__name__, __path__)
