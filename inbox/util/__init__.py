""" Non-server-specific utility modules. These shouldn't depend on any code
    from the inbox module tree!

    Don't add new code here! Find the relevant submodule, or use misc.py if
    there's really no other place.
"""
# Allow out-of-tree submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
