from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.orm import subqueryload, contains_eager
from inbox.models import (Contact, Event, Calendar, Message,
                          MessageContactAssociation, Thread, Tag,
                          TagItem, Block, Part)
from inbox.models.event import RecurringEvent


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
        filters.append(Thread.recentdate < last_message_before)

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
            subqueryload('tagitems').joinedload('tag').
            load_only('public_id', 'name'))

        if view == 'expanded':
            query = query.options(
                subqueryload(Thread.messages).
                load_only('public_id', 'subject', 'is_draft', 'version',
                          'from_addr', 'to_addr', 'cc_addr', 'bcc_addr',
                          'received_date', 'snippet', 'is_read',
                          'reply_to_message_id')
                .joinedload(Message.parts)
                .joinedload(Part.block))

        else:
            query = query.options(
                subqueryload(Thread.messages).
                load_only('public_id', 'is_draft', 'from_addr', 'to_addr',
                          'cc_addr', 'bcc_addr'))

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


def filter_event_query(query, event_cls, namespace_id, event_public_id,
                       calendar_public_id, title, description, location, busy):

    query = query.filter(event_cls.namespace_id == namespace_id)

    if event_public_id:
        query = query.filter(event_cls.public_id == event_public_id)

    if calendar_public_id is not None:
        query = query.join(Calendar). \
            filter(Calendar.public_id == calendar_public_id,
                   Calendar.namespace_id == namespace_id)

    if title is not None:
        query = query.filter(event_cls.title.like('%{}%'.format(title)))

    if description is not None:
        query = query.filter(event_cls.description.like('%{}%'
                                                        .format(description)))

    if location is not None:
        query = query.filter(event_cls.location.like('%{}%'.format(location)))

    if busy is not None:
        query = query.filter(event_cls.busy == busy)

    query = query.filter(event_cls.source == 'local')

    return query


def recurring_events(filters, starts_before, starts_after, ends_before,
                     ends_after, db_session):
    # Expands individual recurring events into full instances.
    # If neither starts_before or ends_before is given, the recurring range
    # defaults to now + 1 year (see events/recurring.py)

    recur_query = db_session.query(RecurringEvent)
    recur_query = filter_event_query(recur_query, RecurringEvent, *filters)

    before_criteria = []
    if starts_before:
        before_criteria.append(RecurringEvent.start < starts_before)
    if ends_before:
        # start < end, so event start < ends_before
        before_criteria.append(RecurringEvent.start < ends_before)
    recur_query = recur_query.filter(and_(*before_criteria))
    after_criteria = []
    if starts_after:
        after_criteria.append(or_(RecurringEvent.until > starts_after,
                                  RecurringEvent.until == None))
    if ends_after:
        after_criteria.append(or_(RecurringEvent.until > ends_after,
                                  RecurringEvent.until == None))

    recur_query = recur_query.filter(and_(*after_criteria))

    recur_instances = []
    for r in recur_query:
        # the occurrences check only checks starting timestamps
        if ends_before and not starts_before:
            starts_before = ends_before - r.length
        if ends_after and not starts_after:
            starts_after = ends_after - r.length
        instances = r.all_events(start=starts_after, end=starts_before)
        recur_instances.extend(instances)

    return recur_instances


def events(namespace_id, event_public_id, calendar_public_id, title,
           description, location, busy, starts_before, starts_after,
           ends_before, ends_after, limit, offset, view,
           expand_recurring, show_cancelled, db_session):

    query = db_session.query(Event)

    if not expand_recurring:
        if view == 'count':
            query = db_session.query(func.count(Event.id))
        elif view == 'ids':
            query = db_session.query(Event.public_id)

    filters = [namespace_id, event_public_id, calendar_public_id,
               title, description, location, busy]
    query = filter_event_query(query, Event, *filters)

    event_criteria = []

    if starts_before is not None:
        event_criteria.append(Event.start < starts_before)

    if starts_after is not None:
        event_criteria.append(Event.start > starts_after)

    if ends_before is not None:
        event_criteria.append(Event.end < ends_before)

    if ends_after is not None:
        event_criteria.append(Event.end > ends_after)

    if not show_cancelled:
        if expand_recurring:
            event_criteria.append(Event.status != 'cancelled')
        else:
            # It doesn't make sense to hide cancelled events
            # when we're not expanding recurring events,
            # so don't do it.
            # We still need to show cancelled recurringevents
            # for those users who want to do event expansion themselves.
            event_criteria.append(
                (Event.discriminator == 'recurringeventoverride') |
                ((Event.status != 'cancelled') & (Event.discriminator !=
                                                  'recurringeventoverride')))

    event_predicate = and_(*event_criteria)
    query = query.filter(event_predicate)

    if expand_recurring:
        expanded = recurring_events(filters, starts_before, starts_after,
                                    ends_before, ends_after, db_session)

        # Combine non-recurring events with expanded recurring ones
        all_events = query.filter(Event.discriminator == 'event').all() + \
            expanded

        if view == 'count':
            return {"count": len(all_events)}

        all_events = sorted(all_events, key=lambda e: e.start)
        if limit:
            offset = offset or 0
            all_events = all_events[offset:offset + limit]
    else:
        if view == 'count':
            return {"count": query.one()[0]}
        query = query.order_by(asc(Event.start)).limit(limit)
        if offset:
            query = query.offset(offset)
        # Eager-load some objects in order to make constructing API
        # representations faster.
        all_events = query.all()

    if view == 'ids':
        return [x[0] for x in all_events]
    else:
        return all_events
