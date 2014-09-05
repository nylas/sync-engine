# Allow out-of-tree submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

try:
    from inbox.client.client import APIClient
    __all__ = ['APIClient']
except ImportError:
    pass
