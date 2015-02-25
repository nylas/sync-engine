from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.orm import subqueryload, contains_eager
from inbox.models import (Contact, Event, Calendar, Message,
                          MessageContactAssociation, Thread, Tag,
                          TagItem, Block, Part)


def threads(namespace_id, subject, from_addr, to_addr, cc_addr, bcc_addr,
            any_email, thread_public_id, started_before, started_after,
            last_message_before, last_message_after, filename, tag, limit,
            offset, view, db_session):

    if view == 'count':
        query = db_session.query(func.count(Thread.id))
    elif view == 'ids':
        query = db_session.query(Thread.public_id)
    else:
        query = db_session.query(Thread)

    filters = [Thread.namespace_id == namespace_id]
    if thread_public_id is not None:
        filters.append(Thread.public_id == thread_public_id)

    if started_before is not None:
        filters.append(Thread.subjectdate < started_before)

    if started_after is not None:
        filters.append(Thread.subjectdate > started_after)

    if last_message_before is not None:
        filters.append(Thread.recentdate <
                               last_message_before)

    if last_message_after is not None:
        filters.append(Thread.recentdate > last_message_after)

    if subject is not None:
        filters.append(Thread.subject == subject)

    query = query.filter(*filters)

    if tag is not None:
        tag_query = db_session.query(TagItem).join(Tag). \
            filter(or_(Tag.public_id == tag, Tag.name == tag),
                   Tag.namespace_id == namespace_id).subquery()

        query = query.join(tag_query)

    if from_addr is not None:
        from_query = db_session.query(Message.thread_id). \
            join(MessageContactAssociation).join(Contact).filter(
                Contact.email_address == from_addr,
                Contact.namespace_id == namespace_id,
                MessageContactAssociation.field == 'from_addr').subquery()
        query = query.filter(Thread.id.in_(from_query))

    if to_addr is not None:
        to_query = db_session.query(Message.thread_id). \
            join(MessageContactAssociation).join(Contact).filter(
                Contact.email_address == to_addr,
                Contact.namespace_id == namespace_id,
                MessageContactAssociation.field == 'to_addr').subquery()
        query = query.filter(Thread.id.in_(to_query))

    if cc_addr is not None:
        cc_query = db_session.query(Message.thread_id). \
            join(MessageContactAssociation).join(Contact).filter(
                Contact.email_address == cc_addr,
                Contact.namespace_id == namespace_id,
                MessageContactAssociation.field == 'cc_addr').subquery()
        query = query.filter(Thread.id.in_(cc_query))

    if bcc_addr is not None:
        bcc_query = db_session.query(Message.thread_id). \
            join(MessageContactAssociation).join(Contact).filter(
                Contact.email_address == bcc_addr,
                Contact.namespace_id == namespace_id,
                MessageContactAssociation.field == 'bcc_addr').subquery()
        query = query.filter(Thread.id.in_(bcc_query))

    if any_email is not None:
        any_contact_query = db_session.query(Message.thread_id). \
            join(MessageContactAssociation).join(Contact). \
            filter(Contact.email_address == any_email,
                   Contact.namespace_id == namespace_id).subquery()
        query = query.filter(Thread.id.in_(any_contact_query))

    if filename is not None:
        files_query = db_session.query(Message.thread_id). \
            join(Part).join(Block). \
            filter(Block.filename == filename,
                   Block.namespace_id == namespace_id). \
            subquery()
        query = query.filter(Thread.id.in_(files_query))
        query = query.join(files_query)

    if view == 'count':
        return {"count": query.one()[0]}

    # Eager-load some objects in order to make constructing API
    # representations faster.
    if view != 'ids':
        query = query.options(
            subqueryload(Thread.messages).
            load_only('public_id', 'is_draft', 'from_addr', 'to_addr',
                      'cc_addr', 'bcc_addr'),
            subqueryload('tagitems').joinedload('tag').
            load_only('public_id', 'name'))

    query = query.order_by(desc(Thread.recentdate)).limit(limit)
    if offset:
        query = query.offset(offset)

    if view == 'ids':
        return [x[0] for x in query.all()]

    return query.all()


def _messages_or_drafts(namespace_id, drafts, subject, from_addr, to_addr,
                        cc_addr, bcc_addr, any_email, thread_public_id,
                        started_before, started_after, last_message_before,
                        last_message_after, filename, tag, limit, offset,
                        view, db_session):

    if view == 'count':
        query = db_session.query(func.count(Message.id))
    elif view == 'ids':
        query = db_session.query(Message.public_id)
    else:
        query = db_session.query(Message)
        query = query.options(contains_eager(Message.thread))

    query = query.join(Thread)

    filters = [Message.namespace_id == namespace_id]
    if drafts:
        filters.append(Message.is_draft)
    else:
        filters.append(~Message.is_draft)

    if subject is not None:
        filters.append(Message.subject == subject)

    if thread_public_id is not None:
        filters.append(Thread.public_id == thread_public_id)

    if started_before is not None:
        filters.append(Thread.subjectdate < started_before)
        filters.append(Thread.namespace_id == namespace_id)

    if started_after is not None:
        filters.append(Thread.subjectdate > started_after)
        filters.append(Thread.namespace_id == namespace_id)

    if last_message_before is not None:
        filters.append(Thread.recentdate < last_message_before)
        filters.append(Thread.namespace_id == namespace_id)

    if last_message_after is not None:
        filters.append(Thread.recentdate > last_message_after)
        filters.append(Thread.namespace_id == namespace_id)

    if tag is not None:
        query = query.join(TagItem).join(Tag). \
            filter(or_(Tag.public_id == tag, Tag.name == tag),
                   Tag.namespace_id == namespace_id)

    if to_addr is not None:
        to_query = db_session.query(MessageContactAssociation.message_id). \
            join(Contact).filter(
                MessageContactAssociation.field == 'to_addr',
                Contact.email_address == to_addr,
                Contact.namespace_id == namespace_id).subquery()
        filters.append(Message.id.in_(to_query))

    if from_addr is not None:
        from_query = db_session.query(MessageContactAssociation.message_id). \
            join(Contact).filter(
                MessageContactAssociation.field == 'from_addr',
                Contact.email_address == from_addr,
                Contact.namespace_id == namespace_id).subquery()
        filters.append(Message.id.in_(from_query))

    if cc_addr is not None:
        cc_query = db_session.query(MessageContactAssociation.message_id). \
            join(Contact).filter(
                MessageContactAssociation.field == 'cc_addr',
                Contact.email_address == cc_addr,
                Contact.namespace_id == namespace_id).subquery()
        filters.append(Message.id.in_(cc_query))

    if bcc_addr is not None:
        bcc_query = db_session.query(MessageContactAssociation.message_id). \
            join(Contact).filter(
                MessageContactAssociation.field == 'bcc_addr',
                Contact.email_address == bcc_addr,
                Contact.namespace_id == namespace_id).subquery()
        filters.append(Message.id.in_(bcc_query))

    if any_email is not None:
        any_email_query = db_session.query(
            MessageContactAssociation.message_id).join(Contact). \
            filter(Contact.email_address == any_email,
                   Contact.namespace_id == namespace_id).subquery()
        filters.append(Message.id.in_(any_email_query))

    if filename is not None:
        query = query.join(Part).join(Block). \
            filter(Block.filename == filename,
                   Block.namespace_id == namespace_id)

    query = query.filter(*filters)

    if view == 'count':
        return {"count": query.one()[0]}

    query = query.order_by(desc(Message.received_date))
    query = query.limit(limit)
    if offset:
        query = query.offset(offset)

    if view == 'ids':
        return [x[0] for x in query.all()]

    # Eager-load related attributes to make constructing API representations
    # faster.
    query = query.options(subqueryload(Message.parts).joinedload(Part.block))

    return query.all()


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


def files(namespace_id, message_public_id, filename, content_type,
          limit, offset, view, db_session):

    if view == 'count':
        query = db_session.query(func.count(Block.id))
    elif view == 'ids':
        query = db_session.query(Block.public_id)
    else:
        query = db_session.query(Block)

    query = query.filter(Block.namespace_id == namespace_id)

    # limit to actual attachments (no content-disposition == not a real
    # attachment)
    query = query.outerjoin(Part)
    query = query.filter(or_(Part.id.is_(None),
                         Part.content_disposition.isnot(None)))

    if content_type is not None:
        query = query.filter(or_(Block._content_type_common == content_type,
                                 Block._content_type_other == content_type))

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

    if view == 'ids':
        return [x[0] for x in query.all()]
    else:
        return query.all()


def events(namespace_id, event_public_id, calendar_public_id, title,
           description, location, starts_before, starts_after, ends_before,
           ends_after, source, limit, offset, view, db_session):

    if view == 'count':
        query = db_session.query(func.count(Event.id))
    elif view == 'ids':
        query = db_session.query(Event.public_id)
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

    if view == 'count':
        return {"count": query.one()[0]}

    query = query.order_by(asc(Event.start)).limit(limit)

    if offset:
        query = query.offset(offset)

    if view == 'ids':
        return [x[0] for x in query.all()]
    else:
        # Eager-load some objects in order to make constructing API
        # representations faster.
        return query.all()
