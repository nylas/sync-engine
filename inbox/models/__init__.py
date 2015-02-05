"""
Caution: subtleties ahead.

It's desirable to ensure that all SQLAlchemy models are imported before you
try to issue any sort of query. The reason you want this assurance is because
if you have mutually dependent relationships between models in separate
files, at least one of those relationships must be specified by a string
reference, in order to avoid circular import errors. But if you haven't
actually imported the referenced model by query time, SQLAlchemy can't resolve
the reference.

Previously, this was accomplished by doing:

from inbox.models.account import Account

etc. right here.

However, this file is part of a namespace package: the contents of
inbox.models.backends may be extended by separately distributed projects.
Thus, those projects also contain their own "inbox/models/__init__.py". If
its contents differ from this one, things break if the wrong __init__ file is
loaded first. But it's painful to have to change all the __init__ files each
time you add a model. So we hoist the actual importing out of this file and
into inbox.models.meta, and engage in a bit of trickery to make model classes
actually available via e.g.
>>> from inbox.models import Account
"""

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
from inbox.models.backends import module_registry as backend_module_registry
from inbox.models.meta import load_models
locals().update({model.__name__: model for model in load_models()})
