from datetime import datetime

from sqlalchemy import (Column, Integer, BigInteger, Boolean, Enum,
                        ForeignKey, Index)
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.sql.expression import false

from inbox.sqlalchemy_ext.util import LittleJSON, JSON, MutableDict

from inbox.log import get_logger
log = get_logger()

from inbox.models.base import MailSyncBase
from inbox.models.account import Account
from inbox.models.thread import Thread
from inbox.models.message import Message
from inbox.models.folder import Folder

PROVIDER = 'imap'


class ImapAccount(Account):
    id = Column(Integer, ForeignKey(Account.id, ondelete='CASCADE'),
                primary_key=True)

    __mapper_args__ = {'polymorphic_identity': 'imapaccount'}

    @property
    def provider(self):
        return PROVIDER.lower()


class ImapUid(MailSyncBase):
    """ Maps UIDs to their IMAP folders and per-UID flag metadata.

    This table is used solely for bookkeeping by the IMAP mail sync backends.
    """
    account_id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                        nullable=False)
    account = relationship(ImapAccount,
                           primaryjoin='and_('
                           'ImapUid.account_id == ImapAccount.id, '
                           'ImapAccount.deleted_at.is_(None))')

    message_id = Column(Integer, ForeignKey(Message.id, ondelete='CASCADE'),
                        nullable=False)
    message = relationship(Message,
                           backref=backref('imapuids',
                                           primaryjoin='and_('
                                           'Message.id == ImapUid.message_id, '
                                           'ImapUid.deleted_at.is_(None))'),
                           primaryjoin='and_('
                           'ImapUid.message_id == Message.id,'
                           'Message.deleted_at.is_(None))')
    msg_uid = Column(BigInteger, nullable=False, index=True)

    folder_id = Column(Integer, ForeignKey(Folder.id, ondelete='CASCADE'),
                       nullable=False)
    # We almost always need the folder name too, so eager load by default.
    folder = relationship(Folder, lazy='joined',
                          backref=backref('imapuids',
                                          passive_deletes=True,
                                          primaryjoin='and_('
                                          'Folder.id == ImapUid.folder_id, '
                                          'ImapUid.deleted_at.is_(None))'),
                          primaryjoin='and_('
                          'ImapUid.folder_id == Folder.id, '
                          'Folder.deleted_at.is_(None))')

    # Flags #
    # Message has not completed composition (marked as a draft).
    is_draft = Column(Boolean, server_default=false(), nullable=False)
    # Message has been read
    is_seen = Column(Boolean, server_default=false(), nullable=False)
    # Message is "flagged" for urgent/special attention
    is_flagged = Column(Boolean, server_default=false(), nullable=False)
    # session is the first session to have been notified about this message
    is_recent = Column(Boolean, server_default=false(), nullable=False)
    # Message has been answered
    is_answered = Column(Boolean, server_default=false(), nullable=False)
    # things like: ['$Forwarded', 'nonjunk', 'Junk']
    extra_flags = Column(LittleJSON, default=[], nullable=False)

    def update_imap_flags(self, new_flags, x_gm_labels=None):
        new_flags = set(new_flags)
        col_for_flag = {
            u'\\Draft': 'is_draft',
            u'\\Seen': 'is_seen',
            u'\\Recent': 'is_recent',
            u'\\Answered': 'is_answered',
            u'\\Flagged': 'is_flagged',
        }
        for flag, col in col_for_flag.iteritems():
            setattr(self, col, flag in new_flags)
            new_flags.discard(flag)
        # Gmail doesn't use the \Draft flag. Go figure.
        if x_gm_labels is not None and '\\Draft' in x_gm_labels:
            self.is_draft = True
        self.extra_flags = sorted(new_flags)

    @property
    def namespace(self):
        return self.imapaccount.namespace

    __table_args__ = (UniqueConstraint('folder_id', 'msg_uid', 'account_id',),)

# make pulling up all messages in a given folder fast
Index('account_id_folder_id', ImapUid.account_id, ImapUid.folder_id)


class ImapFolderInfo(MailSyncBase):
    """ Per-folder UIDVALIDITY and (if applicable) HIGHESTMODSEQ.

    If the UIDVALIDITY value changes, it indicates that all UIDs for messages
    in the folder need to be thrown away and resynced.

    These values come from the IMAP STATUS or SELECT commands.

    See http://tools.ietf.org/html/rfc3501#section-2.3.1.1 for more info
    on UIDVALIDITY, and http://tools.ietf.org/html/rfc4551 for more info on
    HIGHESTMODSEQ.
    """
    account_id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                        nullable=False)
    account = relationship(ImapAccount,
                           primaryjoin='and_('
                           'ImapFolderInfo.account_id == ImapAccount.id, '
                           'ImapAccount.deleted_at == None)')
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'),
                       nullable=False)
    # We almost always need the folder name too, so eager load by default.
    primaryjoin = 'and_(ImapFolderInfo.folder_id == Folder.id, ' \
                  'Folder.deleted_at.is_(None))'
    backrefjoin = 'and_(Folder.id == ImapFolderInfo.folder_id,' \
                  'ImapFolderInfo.deleted_at == None)'
    folder = relationship('Folder', lazy='joined',
                          backref=backref('imapfolderinfo',
                                          primaryjoin=backrefjoin,
                                          passive_deletes=True),
                          primaryjoin=primaryjoin)
    uidvalidity = Column(BigInteger, nullable=False)
    # Invariant: the local datastore for this folder has always incorporated
    # remote changes up to _at least_ this modseq (we can't guarantee that we
    # haven't incorporated later changes too, since IMAP doesn't provide a true
    # transactional interface).
    #
    # Note that some IMAP providers do not support the CONDSTORE extension, and
    # therefore will not use this field.
    highestmodseq = Column(BigInteger, nullable=True)

    __table_args__ = (UniqueConstraint('account_id', 'folder_id'),)


class ImapThread(Thread):
    """ TODO: split into provider-specific classes. """

    id = Column(Integer, ForeignKey(Thread.id, ondelete='CASCADE'),
                primary_key=True)

    # only on messages from Gmail
    #
    # Gmail documents X-GM-THRID as 64-bit unsigned integer. Unique across
    # an account but not necessarily globally unique. The same message sent
    # to multiple users *may* have the same X-GM-THRID, but usually won't.
    g_thrid = Column(BigInteger, nullable=True, index=True, unique=False)

    @classmethod
    def from_gmail_message(cls, session, namespace, message):
        """
        Threads are broken solely on Gmail's X-GM-THRID for now. (Subjects
        are not taken into account, even if they change.)

        Returns the updated or new thread, and adds the message to the thread.
        Doesn't commit.
        """
        if message.thread is not None:
            # If this message *already* has a thread associated with it, just
            # update its g_thrid value.
            message.thread.g_thrid = message.g_thrid
            return message.thread
        if message.g_thrid is not None:
            try:
                return session.query(cls).filter_by(
                    g_thrid=message.g_thrid, namespace_id=namespace.id).one()
            except NoResultFound:
                pass
            except MultipleResultsFound:
                log.error('Duplicate thread rows', g_thrid=message.g_thrid)
                raise
        thread = cls(subject=message.subject, g_thrid=message.g_thrid,
                     recentdate=message.received_date, namespace=namespace,
                     subjectdate=message.received_date,
                     snippet=message.snippet)
        if not message.is_read:
            thread.apply_tag(namespace.tags['unread'])
            thread.apply_tag(namespace.tags['unseen'])
        return thread

    @classmethod
    def from_imap_message(cls, session, namespace, message):
        """ For now, each message is its own thread. """
        if message.thread is not None:
            # If this message *already* has a thread associated with it, don't
            # create a new one.
            return message.thread
        thread = cls(subject=message.subject, recentdate=message.received_date,
                     namespace=namespace, subjectdate=message.received_date,
                     snippet=message.snippet)
        if not message.is_read:
            thread.apply_tag(namespace.tags['unread'])
            thread.apply_tag(namespace.tags['unseen'])
        return thread

    __mapper_args__ = {'polymorphic_identity': 'imapthread'}


class ImapFolderSyncStatus(MailSyncBase):
    """ Per-folder status state saving for IMAP folders. """
    account_id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                        nullable=False)
    account = relationship(ImapAccount, backref=backref(
        'foldersyncstatuses',
        cascade='delete',
        primaryjoin='and_('
        'ImapFolderSyncStatus.account_id == ImapAccount.id, '
        'ImapFolderSyncStatus.deleted_at.is_(None))'),
        primaryjoin='and_('
        'ImapFolderSyncStatus.account_id == ImapAccount.id, '
        'ImapAccount.deleted_at.is_(None))')

    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'),
                       nullable=False)
    # We almost always need the folder name too, so eager load by default.
    folder = relationship('Folder', lazy='joined', backref=backref(
        'imapsyncstatus', primaryjoin='and_('
        'Folder.id == ImapFolderSyncStatus.folder_id, '
        'ImapFolderSyncStatus.deleted_at == None)',
        passive_deletes=True),
        primaryjoin='and_(ImapFolderSyncStatus.folder_id == Folder.id, '
        'Folder.deleted_at == None)')

    # see state machine in mailsync/backends/imap/imap.py
    state = Column(Enum('initial', 'initial uidinvalid',
                   'poll', 'poll uidinvalid', 'finish'),
                   server_default='initial', nullable=False)

    # stats on messages downloaded etc.
    _metrics = Column(MutableDict.as_mutable(JSON), default={}, nullable=True)

    @property
    def metrics(self):
        status = dict(name=self.folder.name, state=self.state)
        status.update(self._metrics or {})

        return status

    def start_sync(self):
        self._metrics = dict(run_state='running',
                             sync_start_time=datetime.utcnow())

    def stop_sync(self):
        self._metrics['run_state'] = 'stopped'
        self._metrics['sync_end_time'] = datetime.utcnow()

    def kill_sync(self, error=None):
        self._metrics['run_state'] = 'killed'
        self._metrics['sync_end_time'] = datetime.utcnow()
        self._metrics['sync_error'] = error

    @property
    def is_killed(self):
        return self._metrics.get('run_state') == 'killed'

    def update_metrics(self, metrics):
        sync_status_metrics = ['remote_uid_count', 'delete_uid_count',
                               'update_uid_count', 'download_uid_count',
                               'uid_checked_timestamp',
                               'num_downloaded_since_timestamp',
                               'queue_checked_at', 'percent']

        assert isinstance(metrics, dict)
        for k in metrics.iterkeys():
            assert k in sync_status_metrics, k

        if self._metrics is not None:
            self._metrics.update(metrics)
        else:
            self._metrics = metrics

    __table_args__ = (UniqueConstraint('account_id', 'folder_id'),)
