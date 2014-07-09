"""
The vault class provides an interface that allows other entities to save and
retrieve 'secrets'. There is a 'LocalVault' which stores these secrets locally,
as well as a 'RemoteVault' stores the secrets through a separate server.
"""

from inbox.config import config
from inbox.models.session import session_scope
from inbox.models.secret import Secret

from sqlalchemy.orm.exc import NoResultFound


class NotFound(Exception):
    pass


class Vault():
    """Abstract class respresenting the vault interface."""
    def get(self, id):
        raise NotImplementedError

    def put(self, value, type=0, acl=0):
        raise NotImplementedError

    def remove(self, id):
        raise NotImplementedError


class LocalVault(Vault):
    """Concrete implementation of the class respresenting the local vault
    interface."""
    def get(self, id):
        with session_scope() as db_session:
            try:
                secret = db_session.query(Secret).filter_by(id=id).one()
                return secret.secret
            except NoResultFound:
                raise NotFound()

    def put(self, value, type=0, acl=0):
        with session_scope() as db_session:
            secret = Secret(secret=value, type=type, acl_id=acl)
            db_session.add(secret)
            db_session.commit()
            return secret.id

    def remove(self, id):
        with session_scope() as db_session:
            secret = db_session.query(Secret).filter_by(id=id).one()
            db_session.delete(secret)
            db_session.commit()


class RemoteVault(Vault):
    """Concrete implementation of the class respresenting the remote vault
    interface."""
    def get(self, id):
        pass

    def put(self, value, type=0, acl=0):
        pass


vault_type = config.get_required("VAULT_TYPE")
assert vault_type in ("remote", "local")
if vault_type == "remote":
    vault = RemoteVault()
else:
    vault = LocalVault()
