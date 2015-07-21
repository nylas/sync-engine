from datetime import datetime

from sqlalchemy import (Column, String, Text, Boolean,
                        UniqueConstraint, ForeignKey, DateTime)
from sqlalchemy.orm import relationship, backref

from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace

from inbox.models.mixins import HasPublicID, HasRevisions


class Calendar(MailSyncBase, HasPublicID, HasRevisions):
    API_OBJECT_NAME = 'calendar'
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)

    namespace = relationship(
        Namespace,
        load_on_pending=True,
        backref=backref('calendars'))

    name = Column(String(128), nullable=True)
    provider_name = Column(String(128), nullable=True, default='DEPRECATED')
    description = Column(Text, nullable=True)

    # A server-provided unique ID.
    uid = Column(String(767, collation='ascii_general_ci'), nullable=False)

    read_only = Column(Boolean, nullable=False, default=False)

    last_synced = Column(DateTime, nullable=True)

    gpush_last_ping = Column(DateTime)
    gpush_expiration = Column(DateTime)

    __table_args__ = (UniqueConstraint('namespace_id', 'provider_name',
                                       'name', 'uid', name='uuid'),)

    def update(self, calendar):
        self.uid = calendar.uid
        self.name = calendar.name
        self.read_only = calendar.read_only
        self.description = calendar.description

    def new_event_watch(self, expiration):
        """
        Google gives us expiration as a timestamp in milliseconds
        """
        expiration = datetime.fromtimestamp(int(expiration) / 1000.)
        self.gpush_expiration = expiration

    def handle_gpush_notification(self):
        self.gpush_last_ping = datetime.utcnow()

    def needs_new_watch(self):
        if self.name == 'Emailed events' and self.uid == 'inbox':
            # This is our own internal calendar
            return False

        # Common to the Birthdays and Holidays calendars.
        # If you try to watch Holidays, you get a 404.
        # If you try to watch Birthdays, you get a cryptic 'Missing Title'
        # error. Thanks, Google.
        if 'group.v.calendar.google.com' in self.uid:
            return False

        return (
            self.gpush_expiration is None or
            self.gpush_expiration < datetime.utcnow()
        )

    def should_update_events(self, max_time_between_syncs):
        """
        max_time_between_syncs: a timedelta object. The maximum amount of
        time we should wait until we sync, even if we haven't received
        any push notifications
        """
        if self.name == 'Emailed events':
            return False
        # TODO: what do we do about calendars we cannot watch?
        if 'group.v.calendar.google.com' in self.uid:
            return False  # maybe?

        return (
            # Never synced
            self.last_synced is None or
            # Push notifications channel is stale
            self.needs_new_watch() or
            # Too much time has passed not to sync
            datetime.utcnow() > self.last_synced + max_time_between_syncs or
            # Events are stale, according to the push notifications
            (
                self.gpush_last_ping is not None and
                self.gpush_last_ping > self.last_synced
            )
        )
