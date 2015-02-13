import datetime
import gevent
from inbox.log import get_logger
from inbox.models import Message
from inbox.models.session import session_scope
from inbox.util.concurrency import retry_and_report_killed
from inbox.util.debug import bind_context

log = get_logger()

DEFAULT_MESSAGE_TTL = 120


class DeleteHandler(gevent.Greenlet):
    """We don't outright delete message objects when all their associated
    uids are deleted. Instead, we mark them by setting a deleted_at
    timestamp. This is so that we can identify when a message is moved between
    folders, or when a draft is updated.

    This class is responsible for periodically checking for marked messages,
    and deleting them for good if they've been marked as deleted for longer
    than message_ttl seconds.

    Parameters
    ----------
    account_id, namespace_id: int
        IDs for the namespace to check.
    uid_accessor: function
        Function that takes a message and returns a list of associated uid
        objects. For IMAP sync, this would just be
        `uid_accessor=lambda m: m.imapuids`
    nessage_ttl: int
        Number of seconds to wait after a message is marked for deletion before
        deleting it for good.
    """
    def __init__(self, account_id, namespace_id, uid_accessor,
                 message_ttl=DEFAULT_MESSAGE_TTL):
        bind_context(self, 'deletehandler', account_id)
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.uids_for_message = uid_accessor
        self.log = log.new(account_id=account_id)
        self.message_ttl = datetime.timedelta(seconds=message_ttl)
        gevent.Greenlet.__init__(self)

    def _run(self):
        return retry_and_report_killed(self._run_impl,
                                       account_id=self.account_id)

    def _run_impl(self):
        while True:
            self.check()
            gevent.sleep(self.message_ttl.total_seconds())

    def check(self):
        current_time = datetime.datetime.utcnow()
        with session_scope() as db_session:
            dangling_messages = db_session.query(Message).filter(
                Message.namespace_id == self.namespace_id,
                Message.deleted_at <= current_time - self.message_ttl)
            for message in dangling_messages:
                # If the message isn't *actually* dangling (i.e., it has
                # imapuids associated with it), undelete it.
                if self.uids_for_message(message):
                    message.deleted_at = None
                    continue

                thread = message.thread
                # Remove message from thread rather than deleting it
                # outright, so that the change to the thread gets properly
                # versioned.
                thread.messages.remove(message)
                if not thread.messages:
                    db_session.delete(thread)
                else:
                    # TODO(emfree): This is messy. We need better
                    # abstractions for recomputing a thread's attributes
                    # from messages, here and in mail sync.
                    non_draft_messages = [m for m in thread.messages if not
                                          m.is_draft]
                    if not non_draft_messages:
                        continue
                    # The value of thread.messages is ordered oldest-to-newest.
                    first_message = non_draft_messages[0]
                    last_message = non_draft_messages[-1]
                    thread.subject = first_message.subject
                    thread.subjectdate = first_message.received_date
                    thread.recentdate = last_message.received_date
                    unread_tag = thread.namespace.tags['unread']
                    attachment_tag = thread.namespace.tags['attachment']
                    if all(m.is_read for m in non_draft_messages):
                        thread.tags.discard(unread_tag)
                    if not any(m.attachments for m in non_draft_messages):
                        thread.tags.discard(attachment_tag)
            db_session.commit()
