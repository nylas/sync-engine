from datetime import datetime

from sqlalchemy import and_, or_

from inbox.server.models.tables.base import (
    Block, Contact, Message, MessageContactAssociation, Thread)


def maybe_refine_query(query, subquery):
    if subquery is None:
        return query
    return query.join(subquery.subquery())


class DatabaseFilter(object):
    """Responsible for constructing database queries out of query parameters.

    Examples
    --------
    >>> from inbox.server.models import session_scope
    >>> filter = DatabaseFilter(namespace_id=1, subject='Welcome to Gmail')
    >>> with session_scope() as db_session:
    ...    msg_query = filter.message_query(db_session)
    ...    print msg_query.all()
    ...    thread_query = filter.message_query(db_session)
    ...    print thread_query.all()
    [<inbox.server.models.tables.base.Message object at 0x3a31810>]
    [<inbox.server.models.tables.imap.ImapThread object at 0x3a3e550>]
    """
    def __init__(self, namespace_id, subject=None, to_addr=None,
                 from_addr=None, cc_addr=None, bcc_addr=None, email=None,
                 started_before=None, started_after=None,
                 last_message_after=None, last_message_before=None,
                 thread_id=None, filename=None, limit=100, offset=0):
        self.namespace_id = namespace_id
        self.subject = subject
        self.to_addr = to_addr
        self.from_addr = from_addr
        self.cc_addr = cc_addr
        self.bcc_addr = bcc_addr
        self.email = email
        self.started_before = started_before
        self.started_after = started_after
        self.last_message_after = last_message_after
        self.last_message_before = last_message_before
        self.thread_id = thread_id
        self.filename = filename
        self.limit = limit
        self.offset = offset

    def message_query(self, db_session):
        """Return a query object which filters messages by the instance's query
        parameters."""
        self.db_session = db_session
        query = self._message_subquery()
        subquery = self._thread_subquery()
        query = maybe_refine_query(query, subquery).distinct()
        if self.limit > 0:
            return query.limit(self.limit).offset(self.offset)
        return query

    def thread_query(self, db_session):
        """Return a query object which filters threads by the instance's query
        parameters."""
        self.db_session = db_session
        query = self._thread_subquery()
        subquery = self._message_subquery()
        # TODO(emfree): If there are no message-specific parameters, we may be
        # doing a join on all messages here. Not ideal.
        query = maybe_refine_query(query, subquery).distinct()
        if self.limit > 0:
            return query.limit(self.limit).offset(self.offset)
        return query

    # The following private methods return individual parts of the eventual
    # composite query.

    def _message_subquery(self):
        query = self.db_session.query(Message)
        if self.subject is not None:
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
        if self.email is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.email,
                Contact.name == self.email))
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _filename_subquery(self):
        if self.filename is None:
            return None
        return self.db_session.query(Block). \
            filter(Block.filename == self.filename)

    def _thread_subquery(self):
        pred = and_(Thread.namespace_id == self.namespace_id)
        if self.thread_id is not None:
            pred = and_(pred, Thread.public_id == self.thread_id)

        if self.started_before is not None:
            pred = and_(pred, Thread.subjectdate <
                        datetime.utcfromtimestamp(self.started_before))

        if self.started_after is not None:
            pred = and_(pred, Thread.subjectdate >
                        datetime.utcfromtimestamp(self.started_after))

        if self.last_message_before is not None:
            pred = and_(pred, Thread.recentdate <
                        datetime.utcfromtimestamp(self.last_message_before))

        if self.last_message_after is not None:
            pred = and_(pred, Thread.recentdate >
                        datetime.utcfromtimestamp(self.last_message_after))

        return self.db_session.query(Thread).filter(pred)
