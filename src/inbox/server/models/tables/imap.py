from sqlalchemy import (Column, Integer, BigInteger, String, Boolean, Enum,
                        ForeignKey, Index)
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.sqlalchemy.util import LittleJSON

from inbox.server.log import get_logger
log = get_logger()

from inbox.server.models import Base
from inbox.server.models.roles import JSONSerializable
from inbox.server.models.tables.base import Account, Thread

PROVIDER = 'Imap'


class ImapAccount(Account):
    id = Column(Integer, ForeignKey('account.id', ondelete='CASCADE'),
                primary_key=True)

    imap_host = Column(String(512))

    __mapper_args__ = {'polymorphic_identity': 'imapaccount'}


class ImapUid(JSONSerializable, Base):
    """ This maps UIDs to the IMAP folder they belong to, and extra metadata
        such as flags.

        This table is used solely for bookkeeping by the IMAP mail sync
        backends.
    """
    imapaccount_id = Column(ForeignKey('imapaccount.id', ondelete='CASCADE'),
                            nullable=False)
    imapaccount = relationship("ImapAccount")
    # If we delete this uid, we also want the associated message to be deleted.
    # Buf if we delete the message, we _don't_ always want to delete the
    # associated uid, we want to be explicit about that (this makes the
    # local data/remote data synchronization work properly). this is why we
    # do not specify the "delete-orphan" cascade option here.
    message_id = Column(Integer, ForeignKey('message.id'), nullable=True)
    message = relationship('Message', cascade="all",
                           backref=backref('imapuid', uselist=False))
    # nullable to allow the local data store to delete messages without
    # deleting the associated uid; we want to leave the uid entry there until
    # we notice the same delete from the backend, which helps our accounting
    # of what is going on. otherwise, it wouldn't make sense to allow these
    # entries to decouple.
    msg_uid = Column(Integer, nullable=True)

    # maximum Gmail label length is 225 (tested empirically), but constraining
    # folder_name uniquely requires max length of 767 bytes under utf8mb4
    # http://mathiasbynens.be/notes/mysql-utf8mb4
    folder_name = Column(String(191))

    ### Flags ###
    # Message has not completed composition (marked as a draft).
    is_draft = Column(Boolean, default=False, nullable=False)
    # Message has been read
    is_seen = Column(Boolean, default=False, nullable=False)
    # Message is "flagged" for urgent/special attention
    is_flagged = Column(Boolean, default=False, nullable=False)
    # session is the first session to have been notified about this message
    is_recent = Column(Boolean, default=False, nullable=False)
    # Message has been answered
    is_answered = Column(Boolean, default=False, nullable=False)
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

    __table_args__ = (UniqueConstraint('folder_name', 'msg_uid',
                      'imapaccount_id',),)

# make pulling up all messages in a given folder fast
Index('imapuid_imapaccount_id_folder_name', ImapUid.imapaccount_id,
      ImapUid.folder_name)


class UIDValidity(JSONSerializable, Base):
    """ UIDValidity has a per-folder value. If it changes, we need to
        re-map g_msgid to UID for that folder.
    """
    imapaccount_id = Column(ForeignKey('imapaccount.id', ondelete='CASCADE'),
                            nullable=False)
    imapaccount = relationship("ImapAccount")
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
    id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
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
        try:
            thread = session.query(cls).filter_by(g_thrid=message.g_thrid,
                                                  namespace=namespace).one()
            return thread.update_from_message(message)
        except NoResultFound:
            pass
        except MultipleResultsFound:
            log.info("Duplicate thread rows for thread {0}".format(
                message.g_thrid))
            raise
        thread = cls(subject=message.subject, g_thrid=message.g_thrid,
                     recentdate=message.received_date, namespace=namespace,
                     subjectdate=message.received_date,
                     mailing_list_headers=message.mailing_list_headers)
        return thread

    __mapper_args__ = {'polymorphic_identity': 'imapthread'}


class FolderSync(Base):
    account_id = Column(ForeignKey('imapaccount.id', ondelete='CASCADE'),
                        nullable=False)
    account = relationship('ImapAccount', backref='foldersyncs')

    # maximum Gmail label length is 225 (tested empirically), but constraining
    # folder_name uniquely requires max length of 767 bytes under utf8mb4
    # http://mathiasbynens.be/notes/mysql-utf8mb4
    folder_name = Column(String(191), nullable=False)

    # see state machine in mailsync/imap.py
    state = Column(Enum('initial', 'initial uidinvalid',
                   'poll', 'poll uidinvalid', 'finish'),
                   default='initial', nullable=False)

    __table_args__ = (UniqueConstraint('account_id', 'folder_name'),)
