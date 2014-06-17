import itertools
import re

from datetime import datetime
import bson

from sqlalchemy import (Column, String, DateTime, ForeignKey, and_,
                        or_, asc, desc)
from sqlalchemy.orm import (reconstructor, relationship, validates,
                            object_session)

from inbox.log import get_logger
log = get_logger()

from inbox.util.encoding import base36decode
from inbox.sqlalchemy_ext.util import Base36UID, maybe_refine_query

from inbox.models.mixins import HasPublicID
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace
from inbox.models.message import Message
from inbox.models.thread import Thread, TagItem
from inbox.models.contact import Contact, MessageContactAssociation
from inbox.models.block import Block
from inbox.models.tag import Tag


LENS_LIMIT_DEFAULT = 100


class Lens(MailSyncBase, HasPublicID):
    """
    The container for a filter to match over data.

    String parameters that begin and end with '/' are interpreted as Python
    regular expressions and matched against the beginning of a string.
    Otherwise exact string matching is applied. Callers using backslashes in
    regexen must either escape them or pass the argument as a raw string (e.g.,
    r'\W+').

    Note: by default, if Lens objects instantiated within a SQLalchemy session,
    they are expunged by default. This is because we often use them to create
    temporary database or transactional filters, and don't want to save those
    filters to the database. If you *do* want to save them (ie: not expunge)
    then set detached=False in the constructor.


    Parameters
    ----------
    email: string or unicode
        Match a name or email address in any of the from, to, cc or bcc fields.
    to_addr, from_addr, cc_addr, bcc_addr: string or unicode
        Match a name or email address in the to, from, cc or bcc fields.
    folder_name: string or unicode
        Match messages contained in the given folder.
    filename: string or unicode
        Match messages that have an attachment matching the given filename.
    thread: integer
        Match messages with given public thread id.
    started_before: datetime.datetime
        Match threads whose first message is dated before the given time.
    started_after: datetime.datetime
        Match threads whose first message is dated after the given time.
    last_message_before: datetime.datetime
        Match threads whose last message is dated before the given time.
    last_message_after: datetime.datetime
        Match threads whose last message is dated after the given time.



    A Lens object can also be used for constructing database queries from
    a given set of parameters.


    Examples
    --------
    >>> from inbox.models.session import session_scope
    >>> filter = Lens(namespace_id=1, subject='Welcome to Gmail')
    >>> with session_scope() as db_session:
    ...    msg_query = filter.message_query(db_session)
    ...    print msg_query.all()
    ...    thread_query = filter.message_query(db_session)
    ...    print thread_query.all()
    [<inbox.models.tables.base.Message object at 0x3a31810>]
    [<inbox.models.tables.imap.ImapThread object at 0x3a3e550>]


    Raises
    ------
    ValueError: If an invalid regex is supplied as a parameter.


    """

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship(
        'Namespace',
        primaryjoin='and_(Lens.namespace_id==Namespace.id, '
                    'Namespace.deleted_at==None)')

    subject = Column(String(255))
    thread_public_id = Column(Base36UID)

    started_before = Column(DateTime)
    started_after = Column(DateTime)
    last_message_before = Column(DateTime)
    last_message_after = Column(DateTime)

    any_email = Column(String(255))
    to_addr = Column(String(255))
    from_addr = Column(String(255))
    cc_addr = Column(String(255))
    bcc_addr = Column(String(255))

    filename = Column(String(255))

    # TODO make tags a reference to the actual column
    tag = Column(String(255))

    # Lenses are constructed from user input, so we need to validate all
    # fields.

    @validates('subject', 'any_email', 'to_addr', 'from_addr', 'cc_addr',
               'bcc_addr', 'filename', 'tag')
    def validate_length(self, key, value):
        if value is None:
            return
        if len(value) > 255:
            raise ValueError('Value for {} is too long'.format(key))
        return value

    @validates('thread_public_id')
    def validate_thread_id(self, key, value):
        if value is None:
            return
        try:
            base36decode(value)
        except ValueError:
            raise ValueError('Invalid thread id')
        return value

    @validates('started_before', 'started_after', 'last_message_before',
               'last_message_after')
    def validate_timestamps(self, key, value):
        if value is None:
            return
        try:
            dt = datetime.utcfromtimestamp(int(value))
            # Need to set tzinfo so that we can compare to datetimes that were
            # deserialized using bson.json_util.
            return dt.replace(tzinfo=bson.tz_util.utc)
        except ValueError:
            raise ValueError('Invalid timestamp value for {}'.format(key))

    def __init__(self, namespace_id=None, subject=None, thread_public_id=None,
                 started_before=None, started_after=None,
                 last_message_before=None, last_message_after=None,
                 any_email=None, to_addr=None, from_addr=None, cc_addr=None,
                 bcc_addr=None, filename=None, tag=None, detached=True):

        self.namespace_id = namespace_id
        self.subject = subject
        self.thread_public_id = thread_public_id
        self.started_before = started_before
        self.started_after = started_after
        self.last_message_before = last_message_before
        self.last_message_after = last_message_after
        self.any_email = any_email
        self.to_addr = to_addr
        self.from_addr = from_addr
        self.cc_addr = cc_addr
        self.bcc_addr = bcc_addr
        self.filename = filename
        self.tag = tag

        if detached and object_session(self) is not None:
            s = object_session(self)
            s.expunge(self)
            # Note, you can later add this object to a session by doing
            # session.merge(detached_objecdt)

        # For transaction filters
        self.filters = []
        self.setup_filters()

    @reconstructor
    def setup_filters(self):

        self.filters = []

        def add_string_filter(filter_string, selector):
            if filter_string is None:
                return

            if filter_string.startswith('/') and filter_string.endswith('/'):
                try:
                    regex = re.compile(filter_string[1:-1])
                except re.error:
                    raise ValueError('Invalid regex argument')
                predicate = regex.match
            else:
                predicate = lambda candidate: filter_string == candidate

            def matcher(message_tx):
                field = selector(message_tx)
                if isinstance(field, basestring):
                    if not predicate(field):
                        return False
                else:
                    if not any(predicate(elem) for elem in field):
                        return False
                return True

            self.filters.append(matcher)

        #
        # Methods related to creating a transactional lens. use `match()`

        def get_subject(message_tx):
            return message_tx.public_snapshot['subject']

        def get_tags(message_tx):
            return [tag['name'] for tag in message_tx.public_snapshot['tags']]

        def flatten_field(field):
            """Given a list of dictionaries, return an iterator over all the
            dictionary values. If field is None, return the empty iterator.

            Parameters
            ----------
            field: list of iterables

            Returns
            -------
            iterable

            Example
            -------
            >>> list(flatten_field([{'name': 'Some Name',
            ...                      'email': 'some email'},
            ...                     {'name': 'Another Name',
            ...                      'email': 'another email'}]))
            ['Name', 'email', 'Another Name', 'another email']
            """
            if field is not None:
                return itertools.chain.from_iterable(d.itervalues() for d in
                                                     field)
            return ()

        def get_to(message_tx):
            return flatten_field(message_tx.public_snapshot['to'])

        def get_from(message_tx):
            return flatten_field(message_tx.public_snapshot['from'])

        def get_cc(message_tx):
            return flatten_field(message_tx.public_snapshot['cc'])

        def get_bcc(message_tx):
            return flatten_field(message_tx.public_snapshot['bcc'])

        def get_emails(message_tx):
            return itertools.chain.from_iterable(
                func(message_tx) for func in (get_to, get_from,
                                              get_cc, get_bcc))

        def get_filenames(message_tx):
            return message_tx.private_snapshot['filenames']

        def get_subject_date(message_tx):
            return message_tx.private_snapshot['subjectdate']

        def get_recent_date(message_tx):
            return message_tx.private_snapshot['recentdate']

        add_string_filter(self.subject, get_subject)
        add_string_filter(self.to_addr, get_to)
        add_string_filter(self.from_addr, get_from)
        add_string_filter(self.cc_addr, get_cc)
        add_string_filter(self.bcc_addr, get_bcc)
        add_string_filter(self.tag, get_tags)
        add_string_filter(self.any_email, get_emails)
        add_string_filter(self.filename, get_filenames)

        if self.thread_public_id is not None:
            self.filters.append(
                lambda message_tx: message_tx.public_snapshot['thread']
                == self.thread_public_id)

        if self.started_before is not None:
            # STOPSHIP(emfree)
            self.filters.append(
                lambda message_tx: (get_subject_date(message_tx) <
                                    self.started_before))

        if self.started_after is not None:
            self.filters.append(
                lambda message_tx: (get_subject_date(message_tx) >
                                    self.started_after))

        if self.last_message_before is not None:
            self.filters.append(
                lambda message_tx: (get_recent_date(message_tx) <
                                    self.last_message_before))

        if self.last_message_after is not None:
            self.filters.append(
                lambda message_tx: (get_recent_date(message_tx) >
                                    self.last_message_after))

    def match(self, message_tx):
        """Returns True if and only if the given message matches all
        filtering criteria."""
        return all(filter_(message_tx) for filter_ in self.filters)

    #
    # Methods related to creating a sqlalchemy filter

    def message_query(self, db_session, limit=None, offset=None, order=None):
        """Return a query object which filters messages by the instance's query
        parameters."""
        limit = limit or LENS_LIMIT_DEFAULT
        offset = offset or 0
        self.db_session = db_session
        query = self._message_subquery()
        query = maybe_refine_query(query, self._thread_subquery())
        query = query.distinct()
        if order == 'subject':
            query = query.order_by(asc(Message.subject))
        elif order == 'date':
            query = query.order_by(desc(Message.received_date))
        else:
            query = query.order_by(asc(Message.id))

        if limit > 0:
            query = query.limit(limit)
        if offset > 0:
            query = query.offset(offset)
        return query

    def thread_query(self, db_session, limit=None, offset=None, order=None):
        """Return a query object which filters threads by the instance's query
        parameters."""
        limit = limit or LENS_LIMIT_DEFAULT
        offset = offset or 0
        self.db_session = db_session
        query = self._thread_subquery()
        # TODO(emfree): If there are no message-specific parameters, we may be
        # doing a join on all messages here. Not good.
        query = maybe_refine_query(query, self._message_subquery())
        query = query.distinct()
        if order == 'subject':
            query = query.order_by(asc(Thread.subject))
        elif order == 'date':
            query = query.order_by(desc(Thread.recentdate))
        else:
            query = query.order_by(asc(Thread.id))

        if limit > 0:
            query = query.limit(limit)
        if offset > 0:
            query = query.offset(offset)
        return query

    # The following private methods return individual parts of the eventual
    # composite query.

    def _message_subquery(self):
        query = self.db_session.query(Message)
        if self.subject is not None:
            # import pdb; pdb.set_trace()
            query = query.filter(Message.subject == self.subject)

        query = maybe_refine_query(query, self._from_subquery())
        query = maybe_refine_query(query, self._to_subquery())
        query = maybe_refine_query(query, self._cc_subquery())
        query = maybe_refine_query(query, self._bcc_subquery())
        query = maybe_refine_query(query, self._email_subquery())
        query = maybe_refine_query(query, self._filename_subquery())
        return query

    def _from_subquery(self):
        if self.from_addr is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.from_addr, Contact.name ==
                self.from_addr),
            MessageContactAssociation.field == 'from_addr')
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _to_subquery(self):
        if self.to_addr is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.to_addr,
                Contact.name == self.to_addr),
            MessageContactAssociation.field == 'to_addr')
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _cc_subquery(self):
        if self.cc_addr is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.cc_addr,
                Contact.name == self.cc_addr),
            MessageContactAssociation.field == 'cc_addr')
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _bcc_subquery(self):
        if self.bcc_addr is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.bcc_addr,
                Contact.name == self.bcc_addr),
            MessageContactAssociation.field == 'bcc_addr')
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _email_subquery(self):
        if self.any_email is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.any_email,
                Contact.name == self.any_email))
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _filename_subquery(self):
        if self.filename is None:
            return None
        return self.db_session.query(Block). \
            filter(Block.filename == self.filename)

    def _tag_subquery(self):
        if self.tag is None:
            return None
        return self.db_session.query(TagItem).join(Tag). \
            filter(or_(Tag.name == self.tag,
                       Tag.public_id == self.tag))

    def _thread_subquery(self):
        pred = and_(Thread.namespace_id == self.namespace_id)
        if self.thread_public_id is not None:
            # TODO(emfree): currently this may return a 500 if
            # thread_public_id isn't b36-decodable.
            pred = and_(pred, Thread.public_id == self.thread_public_id)

        if self.started_before is not None:
            pred = and_(pred, Thread.subjectdate < self.started_before)

        if self.started_after is not None:
            pred = and_(pred, Thread.subjectdate > self.started_after)

        if self.last_message_before is not None:
            pred = and_(pred, Thread.recentdate < self.last_message_before)

        if self.last_message_after is not None:
            pred = and_(pred, Thread.recentdate > self.last_message_after)

        query = self.db_session.query(Thread).filter(pred)
        query = maybe_refine_query(query, self._tag_subquery())

        return query
