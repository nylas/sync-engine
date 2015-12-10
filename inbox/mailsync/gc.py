import datetime

import gevent
from sqlalchemy import func
from nylas.logging import get_logger
log = get_logger()
from inbox.models import Message
from inbox.models.category import Category
from inbox.models.message import MessageCategory
from inbox.models.session import session_scope
from inbox.util.concurrency import retry_with_logging
from inbox.util.debug import bind_context

DEFAULT_MESSAGE_TTL = 120
MAX_FETCH = 1000


class DeleteHandler(gevent.Greenlet):
    """
    We don't outright delete message objects when all their associated
    uids are deleted. Instead, we mark them by setting a deleted_at
    timestamp. This is so that we can identify when a message is moved between
    folders, or when a draft is updated.

    This class is responsible for periodically checking for marked messages,
    and deleting them for good if they've been marked as deleted for longer
    than message_ttl seconds.

    It also periodically deletes categories which have no associated messages.

    Parameters
    ----------
    account_id, namespace_id: int
        IDs for the namespace to check.
    uid_accessor: function
        Function that takes a message and returns a list of associated uid
        objects. For IMAP sync, this would just be
        `uid_accessor=lambda m: m.imapuids`
    message_ttl: int
        Number of seconds to wait after a message is marked for deletion before
        deleting it for good.

    """

    def __init__(self, account_id, namespace_id, provider_name, uid_accessor,
                 message_ttl=DEFAULT_MESSAGE_TTL):
        bind_context(self, 'deletehandler', account_id)
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.provider_name = provider_name
        self.uids_for_message = uid_accessor
        self.log = log.new(account_id=account_id)
        self.message_ttl = datetime.timedelta(seconds=message_ttl)
        gevent.Greenlet.__init__(self)

    def _run(self):
        return retry_with_logging(self._run_impl, account_id=self.account_id,
                                  provider=self.provider_name)

    def _run_impl(self):
        while True:
            current_time = datetime.datetime.utcnow()
            self.check(current_time)
            self.gc_deleted_categories()
            gevent.sleep(self.message_ttl.total_seconds())

    def check(self, current_time):
        with session_scope(self.namespace_id) as db_session:
            dangling_messages = db_session.query(Message).filter(
                Message.namespace_id == self.namespace_id,
                Message.deleted_at <= current_time - self.message_ttl
            ).limit(MAX_FETCH)
            for message in dangling_messages:
                # If the message isn't *actually* dangling (i.e., it has
                # imapuids associated with it), undelete it.
                if self.uids_for_message(message):
                    message.deleted_at = None
                    continue

                thread = message.thread

                if not thread or message not in thread.messages:
                    self.log.warning("Running delete handler check but message"
                                     " is not part of referenced thread: {}",
                                     thread_id=thread.id)
                    # Nothing to check
                    continue

                # Remove message from thread, so that the change to the thread
                # gets properly versioned.
                thread.messages.remove(message)
                # Also need to explicitly delete, so that message shows up in
                # db_session.deleted.
                db_session.delete(message)
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
                    thread.snippet = last_message.snippet
                # YES this is at the right indentation level. Delete statements
                # may cause InnoDB index locks to be acquired, so we opt to
                # simply commit after each delete in order to prevent bulk
                # delete scenarios from creating a long-running, blocking
                # transaction.
                db_session.commit()

    def gc_deleted_categories(self):
        # Delete categories which have been deleted on the backend.
        # Go through all the categories and check if there are messages
        # associated with it. If not, delete it.
        with session_scope(self.namespace_id) as db_session:
            cats = db_session.query(Category).filter(
                Category.namespace_id == self.namespace_id,
                Category.deleted_at != None)

            for cat in cats:
                # Check if no message is associated with the category. If yes,
                # delete it.
                count = db_session.query(func.count(MessageCategory.id)).filter(
                    MessageCategory.category_id == cat.id).scalar()

                if count == 0:
                    db_session.delete(cat)
                    db_session.commit()
