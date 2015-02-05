# Allow out-of-tree action submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
from inbox.util.misc import register_backends
module_registry = register_backends(__name__, __path__)
