from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.orm import joinedload, subqueryload
from inbox.models import (Contact, Event, Calendar, Message,
                          MessageContactAssociation, Thread, Tag,
                          TagItem, Block, Part)


def threads(namespace_id, subject, from_addr, to_addr, cc_addr, bcc_addr,
            any_email, thread_public_id, started_before, started_after,
            last_message_before, last_message_after, filename, tag, limit,
            offset, view, db_session):

    if view == 'count':
        query = db_session.query(func.count(Thread.id))
    else:
        query = db_session.query(Thread)

    thread_criteria = [Thread.namespace_id == namespace_id]
    if thread_public_id is not None:
        query = query.filter(Thread.public_id == thread_public_id)
        # TODO(emfree): at this point there should be at most one object,
        # so we could just execute the query and check additional filters
        # in Python-land.

    if started_before is not None:
        thread_criteria.append(Thread.subjectdate < started_before)

    if started_after is not None:
        thread_criteria.append(Thread.subjectdate > started_after)

    if last_message_before is not None:
        thread_criteria.append(Thread.recentdate <
                               last_message_before)

    if last_message_after is not None:
        thread_criteria.append(Thread.recentdate > last_message_after)

    if subject is not None:
        thread_criteria.append(Thread.subject == subject)

    thread_predicate = and_(*thread_criteria)
    query = query.filter(thread_predicate)

    if tag is not None:
        tag_query = db_session.query(TagItem).join(Tag). \
            filter(or_(Tag.public_id == tag, Tag.name == tag),
                   Tag.namespace_id == namespace_id).subquery()

        query = query.join(tag_query)

    if any((from_addr, to_addr, cc_addr, bcc_addr)):
        contact_criteria = []
        if from_addr is not None:
            contact_criteria.append(and_(
                Contact.email_address == from_addr,
                MessageContactAssociation.field == 'from_addr'))

        if to_addr is not None:
            contact_criteria.append(and_(
                Contact.email_address == to_addr,
                MessageContactAssociation.field == 'to_addr'))

        if cc_addr is not None:
            contact_criteria.append(and_(
                Contact.email_address == cc_addr,
                MessageContactAssociation.field == 'cc_addr'))

        if bcc_addr is not None:
            contact_criteria.append(and_(
                Contact.email_address == bcc_addr,
                MessageContactAssociation.field == 'bcc_addr'))

        contact_query = db_session.query(Message). \
            join(MessageContactAssociation).join(Contact). \
            filter(or_(*contact_criteria)).subquery()

        query = query.join(contact_query)

    if any_email is not None:
        any_contact_query = db_session.query(Message). \
            join(MessageContactAssociation).join(Contact). \
            filter(Contact.email_address == any_email).subquery()
        query = query.join(any_contact_query)

    if filename is not None:
        files_query = db_session.query(Message). \
            join(Part).join(Block). \
            filter(Block.filename == filename). \
            subquery()
        query = query.join(files_query)

    if view == 'count':
        return {"count": query.one()[0]}

    # Eager-load some objects in order to make constructing API
    # representations faster.
    query = query.options(
        subqueryload(Thread.messages).
        load_only('public_id', 'is_draft', 'from_addr', 'to_addr',
                  'cc_addr', 'bcc_addr'),
        subqueryload('tagitems').joinedload('tag').
        load_only('public_id', 'name'))

    query = query.order_by(desc(Thread.recentdate)).distinct().limit(limit)
    if offset:
        query = query.offset(offset)

    return query.all()


def _messages_or_drafts(namespace_id, drafts, subject, from_addr, to_addr,
                        cc_addr, bcc_addr, any_email, thread_public_id,
                        started_before, started_after, last_message_before,
                        last_message_after, filename, tag, limit, offset,
                        view, db_session):

    if view == 'count':
        id_query = db_session.query(func.count(Message.id))
    else:
        id_query = db_session.query(Message.id)

    if drafts:
        id_query = id_query.filter(Message.is_draft)
    else:
        id_query = id_query.filter(~Message.is_draft)

    thread_criteria = [Thread.namespace_id == namespace_id]

    if thread_public_id is not None:
        # TODO(emfree) this is a common case that we should handle
        # separately by just fetching the thread's messages and only
        # filtering more if needed.
        thread_criteria.append(Thread.public_id == thread_public_id)

    if started_before is not None:
        thread_criteria.append(Thread.subjectdate < started_before)

    if started_after is not None:
        thread_criteria.append(Thread.subjectdate > started_after)

    if last_message_before is not None:
        thread_criteria.append(Thread.recentdate <
                               last_message_before)

    if last_message_after is not None:
        thread_criteria.append(Thread.recentdate > last_message_after)

    thread_predicate = and_(*thread_criteria)
    thread_query = db_session.query(Thread).filter(thread_predicate)
    if tag is not None:
        thread_query = thread_query.join(TagItem).join(Tag). \
            filter(or_(Tag.public_id == tag, Tag.name == tag),
                   Tag.namespace_id == namespace_id)
    thread_query = thread_query.subquery()

    id_query = id_query.join(thread_query)

    if subject is not None:
        id_query = id_query.filter(Message.subject == subject)

    if to_addr is not None:
        to_query = db_session.query(Message). \
            join(MessageContactAssociation).join(Contact). \
            filter(MessageContactAssociation.field == 'to_addr',
                   Contact.email_address == to_addr).subquery()
        id_query = id_query.join(to_query)

    if from_addr is not None:
        from_query = db_session.query(MessageContactAssociation). \
            join(Contact).filter(
                MessageContactAssociation.field == 'from_addr',
                Contact.email_address == from_addr).subquery()
        id_query = id_query.join(from_query)

    if cc_addr is not None:
        cc_query = db_session.query(MessageContactAssociation). \
            join(Contact).filter(
                MessageContactAssociation.field == 'cc_addr',
                Contact.email_address == cc_addr).subquery()
        id_query = id_query.join(cc_query)

    if bcc_addr is not None:
        bcc_query = db_session.query(MessageContactAssociation). \
            join(Contact).filter(
                MessageContactAssociation.field == 'bcc_addr',
                Contact.email_address == bcc_addr).subquery()
        id_query = id_query.join(bcc_query)

    if any_email is not None:
        any_email_query = db_session.query(
            MessageContactAssociation).join(Contact). \
            filter(Contact.email_address == any_email).subquery()
        id_query = id_query.join(any_email_query)

    if filename is not None:
        id_query = id_query.join(Part).join(Block). \
            filter(Block.filename == filename,
                   Block.namespace_id == namespace_id)

    if not drafts:
        id_query = id_query.order_by(desc(Message.received_date))

    if view == 'count':
        return {"count": id_query.one()[0]}

    id_query = id_query.distinct().limit(limit)
    if offset:
        id_query = id_query.offset(offset)

    ids = [id for id, in id_query.all()]
    if not ids:
        # Short-circuit to avoid evaluating in-predicate with empty sequence
        # below, which causes SAWarning.
        return []
    # Eager-load part.content_disposition to make constructing API
    # representations faster
    messages_query = db_session.query(Message).filter(Message.id.in_(ids)). \
        options(joinedload(Message.parts).load_only('content_disposition'))
    if not drafts:
        messages_query = messages_query.order_by(desc(Message.received_date))

    return messages_query.all()


def messages(namespace_id, subject, from_addr, to_addr, cc_addr, bcc_addr,
             any_email, thread_public_id, started_before, started_after,
             last_message_before, last_message_after, filename, tag, limit,
             offset, view, db_session):
    return _messages_or_drafts(namespace_id, False, subject, from_addr,
                               to_addr, cc_addr, bcc_addr, any_email,
                               thread_public_id, started_before,
                               started_after, last_message_before,
                               last_message_after, filename, tag, limit,
                               offset, view, db_session)


def drafts(namespace_id, subject, from_addr, to_addr, cc_addr, bcc_addr,
           any_email, thread_public_id, started_before, started_after,
           last_message_before, last_message_after, filename, tag, limit,
           offset, view, db_session):
    return _messages_or_drafts(namespace_id, True, subject, from_addr,
                               to_addr, cc_addr, bcc_addr, any_email,
                               thread_public_id, started_before,
                               started_after, last_message_before,
                               last_message_after, filename, tag, limit,
                               offset, view, db_session)


def files(namespace_id, file_public_id, message_public_id, filename,
          content_type, is_attachment, limit, offset, view, db_session):

    if view == 'count':
        query = db_session.query(func.count(Block.id))
    else:
        query = db_session.query(Block)

    query = query.filter(Block.namespace_id == namespace_id)

    # filter out inline attachments while keeping non-attachments
    query = query.outerjoin(Part)
    if is_attachment is True:
        query = query.filter(Part.content_disposition,
                             Part.content_disposition != 'inline')
    elif is_attachment is False:
        query = query.filter(Part.id.is_(None))
    else:
        query = query.filter(or_(Part.id.is_(None),
                             and_(Part.content_disposition,
                                  Part.content_disposition != 'inline')))

    if content_type is not None:
        query = query.filter(or_(Block._content_type_common == content_type,
                                 Block._content_type_other == content_type))

    if file_public_id is not None:
        query = query.filter(Block.public_id == file_public_id)

    if filename is not None:
        query = query.filter(Block.filename == filename)

    # Handle the case of fetching attachments on a particular message.
    if message_public_id is not None:
        query = query.join(Message) \
            .filter(Message.public_id == message_public_id)

    if view == 'count':
        return {"count": query.one()[0]}

    query = query.order_by(asc(Block.id)).distinct().limit(limit)

    if offset:
        query = query.offset(offset)

    return query.all()


def events(namespace_id, event_public_id, calendar_public_id, title,
           description, location, starts_before, starts_after, ends_before,
           ends_after, source, limit, offset, view, db_session):

    if view == 'count':
        query = db_session.query(func.count(Event.id))
    else:
        query = db_session.query(Event)

    query = query.filter(Event.namespace_id == namespace_id)

    event_criteria = []
    if event_public_id:
        query = query.filter(Event.public_id == event_public_id)

    if starts_before is not None:
        event_criteria.append(Event.start < starts_before)

    if starts_after is not None:
        event_criteria.append(Event.start > starts_after)

    if ends_before is not None:
        event_criteria.append(Event.end < ends_before)

    if ends_after is not None:
        event_criteria.append(Event.end > ends_after)

    event_predicate = and_(*event_criteria)
    query = query.filter(event_predicate)

    if calendar_public_id is not None:
        query = query.join(Calendar). \
            filter(Calendar.public_id == calendar_public_id,
                   Calendar.namespace_id == namespace_id)

    if title is not None:
        query = query.filter(Event.title.like('%{}%'.format(title)))

    if description is not None:
        query = query.filter(Event.description.like('%{}%'
                                                    .format(description)))

    if location is not None:
        query = query.filter(Event.location.like('%{}%'.format(location)))

    if source is not None:
        query = query.filter(Event.source == source)

    # Eager-load some objects in order to make constructing API
    # representations faster.
    query = query.options(
        subqueryload(Event.participants_by_email))

    if view == 'count':
        return {"count": query.one()[0]}

    query = query.order_by(asc(Event.start)).limit(limit)
    if offset:
        query = query.offset(offset)

    return query.all()
