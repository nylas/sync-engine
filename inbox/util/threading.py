# -*- coding: utf-8 -*-
from inbox.sqlalchemy_ext.util import safer_yield_per
from inbox.models.thread import Thread
from sqlalchemy import desc
from inbox.util.misc import cleanup_subject


MAX_THREAD_LENGTH = 500


def fetch_corresponding_thread(db_session, namespace_id, message):
    """fetch a thread matching the corresponding message. Returns None if
       there's no matching thread."""
    # FIXME: for performance reasons, we make the assumption that a reply
    # to a message always has a similar subject. This is only
    # right 95% of the time.
    clean_subject = cleanup_subject(message.subject)
    threads = db_session.query(Thread).filter(
        Thread.namespace_id == namespace_id,
        Thread._cleaned_subject == clean_subject). \
        order_by(desc(Thread.id))

    for thread in safer_yield_per(threads, Thread.id, 0, 100):
        for match in thread.messages:
            # A lot of people BCC some address when sending mass
            # emails so ignore BCC.
            match_bcc = match.bcc_addr if match.bcc_addr else []
            message_bcc = message.bcc_addr if message.bcc_addr else []

            match_emails = [t[1] for t in match.participants
                            if t not in match_bcc]
            message_emails = [t[1] for t in message.participants
                              if t not in message_bcc]

            # A conversation takes place between two or more persons.
            # Are there more than two participants in common in this
            # thread? If yes, it's probably a related thread.
            match_participants_set = set(match_emails)
            message_participants_set = set(message_emails)

            if len(match_participants_set & message_participants_set) >= 2:
                # No need to loop through the rest of the messages
                # in the thread
                if len(thread.messages) >= MAX_THREAD_LENGTH:
                    break
                else:
                    return match.thread

            # handle the case where someone is self-sending an email.
            if not message.from_addr or not message.to_addr:
                return

            match_from = [t[1] for t in match.from_addr]
            match_to = [t[1] for t in match.from_addr]
            message_from = [t[1] for t in message.from_addr]
            message_to = [t[1] for t in message.to_addr]

            if (len(message_to) == 1 and message_from == message_to and
                    match_from == match_to and message_to == match_from):
                # Check that we're not over max thread length in this case
                # No need to loop through the rest of the messages
                # in the thread.
                if len(thread.messages) >= MAX_THREAD_LENGTH:
                    break
                else:
                    return match.thread

    return
