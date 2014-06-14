from sqlalchemy import (Column, Integer, BigInteger, String, Boolean, Enum,
                        ForeignKey, Index)
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.sql.expression import false

from inbox.sqlalchemy_ext.util import LittleJSON

from inbox.log import get_logger
log = get_logger()

from inbox.models.base import MailSyncBase
from inbox.models.account import Account
from inbox.models.thread import Thread
from inbox.models.message import Message
from inbox.models.folder import Folder

# Note: Imap IS Gmail currently
PROVIDER = 'Gmail'


class ImapAccount(Account):
    id = Column(Integer, ForeignKey(Account.id, ondelete='CASCADE'),
                primary_key=True)

    imap_host = Column(String(512))

    given_name = Column(String(255))
    family_name = Column(String(255))
    g_locale = Column(String(16))
    g_picture_url = Column(String(255))
    g_gender = Column(String(16))
    g_plus_url = Column(String(255))
    google_id = Column(String(255))

    @property
    def full_name(self):
        return '{0} {1}'.format(self.given_name, self.family_name)

    __mapper_args__ = {'polymorphic_identity': 'imapaccount'}


class ImapUid(MailSyncBase):
    """ This maps UIDs to the IMAP folder they belong to, and extra metadata
        such as flags.

        This table is used solely for bookkeeping by the IMAP mail sync
        backends.
    """
    imapaccount_id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                            nullable=False)
    imapaccount = relationship('ImapAccount',
                               primaryjoin='and_('
                               'ImapUid.imapaccount_id == ImapAccount.id, '
                               'ImapAccount.deleted_at.is_(None))')

    message_id = Column(Integer, ForeignKey(Message.id), nullable=False)
    message = relationship('Message',
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
    folder = relationship('Folder', lazy='joined',
                          backref=backref('imapuids',
                                          passive_deletes=True,
                                          primaryjoin='and_('
                                          'Folder.id == ImapUid.folder_id, '
                                          'ImapUid.deleted_at.is_(None))'),
                          primaryjoin='and_('
                          'ImapUid.folder_id == Folder.id, '
                          'Folder.deleted_at.is_(None))')

    ### Flags ###
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
    extra_flags = Column(LittleJSON, nullable=False)

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

    __table_args__ = (UniqueConstraint('folder_id', 'msg_uid',
                      'imapaccount_id',),)

# make pulling up all messages in a given folder fast
Index('imapaccount_id_folder_id', ImapUid.imapaccount_id, ImapUid.folder_id)


class UIDValidity(MailSyncBase):
    """ UIDValidity has a per-folder value. If it changes, we need to
        re-map g_msgid to UID for that folder.
    """
    imapaccount_id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                            nullable=False)
    imapaccount = relationship("ImapAccount",
                               primaryjoin='and_('
                               'UIDValidity.imapaccount_id == ImapAccount.id, '
                               'ImapAccount.deleted_at.is_(None))')
    # maximum Gmail label length is 225 (tested empirically), but constraining
    # folder_name uniquely requires max length of 767 bytes under utf8mb4
    # http://mathiasbynens.be/notes/mysql-utf8mb4
    folder_name = Column(String(191), nullable=False)
    uid_validity = Column(Integer, nullable=False)
    # invariant: the local datastore for this folder has always incorporated
    # remote changes up to _at least_ this modseq (we can't guarantee that
    # we haven't incorporated later changes too, since IMAP doesn't provide
    # a true transactional interface)
    highestmodseq = Column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint('imapaccount_id', 'folder_name'),)


class ImapThread(Thread):
    id = Column(Integer, ForeignKey(Thread.id, ondelete='CASCADE'),
                primary_key=True)

    # only on messages from Gmail
    # NOTE: The same message sent to multiple users will be given a
    # different g_thrid for each user. We don't know yet if g_thrids are
    # unique globally.

    # Gmail documents X-GM-THRID as 64-bit unsigned integer
    g_thrid = Column(BigInteger, nullable=True, index=True)

    @classmethod
    def from_gmail_message(cls, session, namespace, message):
        """
        Threads are broken solely on Gmail's X-GM-THRID for now. (Subjects
        are not taken into account, even if they change.)

        Returns the updated or new thread, and adds the message to the thread.
        Doesn't commit.
        """
        if message.g_thrid is not None:
            try:
                thread = session.query(cls).filter_by(
                    g_thrid=message.g_thrid, namespace=namespace).one()
                return thread.update_from_message(message)
            except NoResultFound:
                pass
            except MultipleResultsFound:
                log.info('Duplicate thread rows for thread {0}'.format(
                    message.g_thrid))
                raise
        thread = cls(subject=message.subject, g_thrid=message.g_thrid,
                     recentdate=message.received_date, namespace=namespace,
                     subjectdate=message.received_date,
                     mailing_list_headers=message.mailing_list_headers)
        if not message.is_read:
            thread.apply_tag(namespace.tags['unread'])
        return thread

    __mapper_args__ = {'polymorphic_identity': 'imapthread'}


class FolderSync(MailSyncBase):
    account_id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                        nullable=False)
    account = relationship('ImapAccount', backref=backref(
        'foldersyncs',
        primaryjoin='and_('
        'FolderSync.account_id == ImapAccount.id, '
        'FolderSync.deleted_at.is_(None))'),
        primaryjoin='and_('
        'FolderSync.account_id == ImapAccount.id, '
        'ImapAccount.deleted_at.is_(None))')

    # maximum Gmail label length is 225 (tested empirically), but constraining
    # folder_name uniquely requires max length of 767 bytes under utf8mb4
    # http://mathiasbynens.be/notes/mysql-utf8mb4
    folder_name = Column(String(191), nullable=False)

    # see state machine in mailsync/imap.py
    state = Column(Enum('initial', 'initial uidinvalid',
                   'poll', 'poll uidinvalid', 'finish'),
                   server_default='initial', nullable=False)

    __table_args__ = (UniqueConstraint('account_id', 'folder_name'),)
