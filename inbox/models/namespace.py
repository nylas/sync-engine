from sqlalchemy import Column, Integer, Enum, ForeignKey
from sqlalchemy.orm import relationship, backref

from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID


class Namespace(MailSyncBase, HasPublicID):
    """ A way to do grouping / permissions, basically. """
    def __init__(self):
        self.create_canonical_tags()

    # NOTE: only root namespaces have account backends
    account_id = Column(Integer,
                        ForeignKey('account.id', ondelete='CASCADE'),
                        nullable=True)
    # really the root_namespace
    account = relationship('Account',
                           lazy='joined',
                           single_parent=True,
                           backref=backref('namespace', uselist=False,
                                           lazy='joined'),
                           uselist=False)

    # invariant: imapaccount is non-null iff type is root
    type = Column(Enum('root', 'shared_folder'), nullable=False,
                  server_default='root')

    @property
    def email_address(self):
        if self.account is not None:
            return self.account.email_address

    def create_canonical_tags(self):
        """If they don't already exist yet, create tags that should always
        exist."""
        from inbox.models.tag import Tag
        # namespace.tags is a dictionary mapping tag public id to tag object.
        existing_canonical_tag_names = {name for name in self.tags if name in
                                        Tag.CANONICAL_TAG_NAMES}
        missing_canonical_names = set(Tag.CANONICAL_TAG_NAMES).difference(
            existing_canonical_tag_names)
        for canonical_name in missing_canonical_names:
            tag = Tag(public_id=canonical_name, name=canonical_name)
            self.tags[canonical_name] = tag
