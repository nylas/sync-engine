from datetime import datetime
import bson
from sqlalchemy import and_, or_, asc, desc
from sqlalchemy.orm import joinedload, subqueryload
from inbox.models import (Contact, Message, MessageContactAssociation, Thread,
                          Tag, TagItem, Part)
from inbox.util.encoding import base36decode


class Filter(object):
    """ A container for all the filtering query parameters an API client may
    pass."""
    def __init__(self, namespace_id, subject, from_addr, to_addr, cc_addr,
                 bcc_addr, any_email, thread_public_id, started_before,
                 started_after, last_message_before, last_message_after,
                 filename, tag, limit, offset, order_by, db_session):
        self.namespace_id = namespace_id
        self.subject = subject
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.cc_addr = cc_addr
        self.bcc_addr = bcc_addr
        self.any_email = any_email
        self.thread_public_id = thread_public_id
        self.started_before = started_before
        self.started_after = started_after
        self.last_message_before = last_message_before
        self.last_message_after = last_message_after
        self.filename = filename
        self.tag = tag
        self.limit = limit
        self.offset = offset
        self.order_by = order_by
        self.db_session = db_session

        # Validate input

        for key in ('subject', 'any_email', 'to_addr', 'from_addr', 'cc_addr',
                    'bcc_addr', 'filename', 'tag'):
            value = getattr(self, key, None)
            if value is not None and len(value) > 255:
                raise ValueError('Value {} for {} is too long'.
                                 format(value, key))

        if thread_public_id is not None:
            try:
                base36decode(thread_public_id)
            except ValueError:
                raise ValueError('Invalid thread id {}'.
                                 format(thread_public_id))

        for key in ('started_before', 'started_after', 'last_message_before',
                    'last_message_after'):
            value = getattr(self, key, None)
            if value is not None:
                try:
                    # Replace Unix timestamp by datetime object.
                    # We need to set tzinfo so that we can compare to datetimes
                    # that were deserialized using bson.json_util.
                    dt = datetime.utcfromtimestamp(int(value))
                    setattr(self, key, dt.replace(tzinfo=bson.tz_util.utc))
                except ValueError:
                    raise ValueError('Invalid timestamp value {} for {}'.
                                     format(value, key))

    def get_threads(self):
        query = self.db_session.query(Thread)
        thread_criteria = [Thread.namespace_id == self.namespace_id]
        if self.thread_public_id is not None:
            query = query.filter(Thread.public_id ==
                                 self.thread_public_id)
            # TODO(emfree): at this point there should be at most one object,
            # so we could just execute the query and check additional filters
            # in Python-land.

        if self.started_before is not None:
            thread_criteria.append(Thread.subjectdate < self.started_before)

        if self.started_after is not None:
            thread_criteria.append(Thread.subjectdate > self.started_after)

        if self.last_message_before is not None:
            thread_criteria.append(Thread.recentdate <
                                   self.last_message_before)

        if self.last_message_after is not None:
            thread_criteria.append(Thread.recentdate > self.last_message_after)

        if self.subject is not None:
            thread_criteria.append(Thread.subject == self.subject)

        thread_predicate = and_(*thread_criteria)
        query = query.filter(thread_predicate)

        if self.tag is not None:
            tag_query = self.db_session.query(TagItem).join(Tag). \
                filter(or_(Tag.public_id == self.tag,
                           Tag.name == self.tag)).subquery()

            query = query.join(tag_query)

        if any((self.from_addr, self.to_addr, self.cc_addr, self.bcc_addr)):
            contact_criteria = []
            for field in ('from_addr', 'to_addr', 'cc_addr', 'bcc_addr'):
                if getattr(self, field, None) is not None:
                    contact_criteria.append(and_(
                        Contact.email_address == getattr(self, field),
                        MessageContactAssociation.field == field))

            contact_query = self.db_session.query(Message). \
                join(MessageContactAssociation).join(Contact). \
                filter(or_(*contact_criteria)).subquery()

            query = query.join(contact_query)

        if self.any_email is not None:
            any_contact_query = self.db_session.query(Message). \
                join(MessageContactAssociation).join(Contact). \
                filter(Contact.email_address == self.any_email).subquery()
            query = query.join(any_contact_query)

        if self.filename is not None:
            files_query = self.db_session.query(Message). \
                join(Part).filter(Part.filename == self.filename).subquery()
            query = query.join(files_query)

        # Eager-load some objects in order to make constructing API
        # representations faster.
        query = query.options(
            subqueryload(Thread.messages).
            load_only('public_id', 'is_draft', 'from_addr', 'to_addr',
                      'cc_addr', 'bcc_addr'),
            subqueryload('tagitems').joinedload('tag').
            load_only('public_id', 'name'))

        if self.order_by == 'subject':
            query = query.order_by(asc(Thread.subject))
        elif self.order_by == 'date':
            query = query.order_by(desc(Thread.recentdate))

        query = query.limit(self.limit)
        if self.offset:
            query = query.offset(self.offset)
        return query.all()

    def get_messages(self):
        query = self.db_session.query(Message). \
            filter(Message.is_draft == False)

        thread_criteria = [Thread.namespace_id == self.namespace_id]

        if self.thread_public_id is not None:
            # TODO(emfree) this is a common case that we should handle
            # separately by just fetching the thread's messages and only
            # filtering more if needed.
            thread_criteria.append(Thread.public_id == self.thread_public_id)

        if self.started_before is not None:
            thread_criteria.append(Thread.subjectdate < self.started_before)

        if self.started_after is not None:
            thread_criteria.append(Thread.subjectdate > self.started_after)

        if self.last_message_before is not None:
            thread_criteria.append(Thread.recentdate <
                                   self.last_message_before)

        if self.last_message_after is not None:
            thread_criteria.append(Thread.recentdate > self.last_message_after)

        thread_predicate = and_(*thread_criteria)
        thread_query = self.db_session.query(Thread).filter(thread_predicate)
        if self.tag is not None:
            thread_query = thread_query.join(TagItem).join(Tag). \
                filter(or_(Tag.public_id == self.tag, Tag.name == self.tag))
        thread_query = thread_query.subquery()

        query = query.join(thread_query)

        if self.subject is not None:
            query = query.filter(Message.subject == self.subject)

        if self.to_addr is not None:
            to_query = self.db_session.query(Message). \
                join(MessageContactAssociation).join(Contact). \
                filter(MessageContactAssociation.field == 'to_addr',
                       Contact.email_address == self.to_addr).subquery()
            query = query.join(to_query)

        if self.from_addr is not None:
            from_query = self.db_session.query(MessageContactAssociation). \
                join(Contact).filter(
                    MessageContactAssociation.field == 'from_addr',
                    Contact.email_address == self.from_addr).subquery()
            query = query.join(from_query)

        if self.cc_addr is not None:
            cc_query = self.db_session.query(MessageContactAssociation). \
                join(Contact).filter(
                    MessageContactAssociation.field == 'cc_addr',
                    Contact.email_address == self.cc_addr).subquery()
            query = query.join(cc_query)

        if self.bcc_addr is not None:
            bcc_query = self.db_session.query(MessageContactAssociation). \
                join(Contact).filter(
                    MessageContactAssociation.field == 'bcc_addr',
                    Contact.email_address == self.bcc_addr).subquery()
            query = query.join(bcc_query)

        if self.any_email is not None:
            any_email_query = self.db_session.query(
                MessageContactAssociation).join(Contact). \
                filter(Contact.email_address == self.any_email).subquery()
            query = query.join(any_email_query)

        if self.filename is not None:
            file_query = self.db_session.query(Part). \
                filter(Part.filename == self.filename).subquery()
            query = query.join(file_query)

        # Eager-load some objects in order to make constructing API
        # representations faster.
        query = query.options(
            joinedload(Message.parts).load_only('public_id',
                                                'content_disposition'),
            joinedload(Message.thread).load_only('public_id', 'discriminator'))

        # TODO(emfree) we should really eager-load the namespace too
        # (or just directly store it on the message object)

        if self.order_by == 'subject':
            query = query.order_by(asc(Message.subject))
        elif self.order_by == 'date':
            query = query.order_by(desc(Message.received_date))

        query = query.limit(self.limit)
        if self.offset:
            query = query.offset(self.offset)

        return query.all()
