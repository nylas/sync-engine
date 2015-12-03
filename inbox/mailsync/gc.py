import datetime
from imapclient.imap_utf7 import encode as utf7_encode

import gevent
from sqlalchemy import func
from nylas.logging import get_logger
log = get_logger()
from inbox.models import Message
from inbox.models.category import Category
from inbox.models.message import MessageCategory
from inbox.models.folder import Folder
from inbox.models.session import session_scope
from inbox.util.concurrency import retry_with_logging
from inbox.mailsync.backends.imap import common
from inbox.util.debug import bind_context
from inbox.mailsync.backends.imap.generic import uidvalidity_cb
from inbox.crispin import connection_pool

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


class LabelRenameHandler(gevent.Greenlet):
    """
    Gmail has a long-standing bug where it won't notify us
    of a label rename (https://stackoverflow.com/questions/19571456/how-imap-client-can-detact-gmail-label-rename-programmatically).

    Because of this, we manually refresh the labels for all the UIDs in
    this label. To do this, we select all the folders we sync and run a search
    for the uids holding the new label.

    This isn't elegant but it beats having to issue a complex query to the db.

    """
    def __init__(self, account_id, namespace_id, label_name,
                 message_ttl=DEFAULT_MESSAGE_TTL):
        bind_context(self, 'renamehandler', account_id)
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.label_name = label_name
        self.log = log.new(account_id=account_id)
        gevent.Greenlet.__init__(self)

    def _run(self):
        return retry_with_logging(self._run_impl, account_id=self.account_id)

    def _run_impl(self):
        self.log.info('Starting LabelRenameHandler',
                      label_name=self.label_name)

        with connection_pool(self.account_id).get() as crispin_client:
            folder_names = []
            with session_scope(self.account_id) as db_session:
                folders = db_session.query(Folder).filter(
                    Folder.account_id == self.account_id)

                folder_names = [folder.name for folder in folders]
                db_session.expunge_all()

            for folder_name in folder_names:
                crispin_client.select_folder(folder_name, uidvalidity_cb)

                found_uids = crispin_client.search_uids(
                    ['X-GM-LABELS', utf7_encode(self.label_name)])
                flags = crispin_client.flags(found_uids)

                self.log.info('Running metadata update for folder',
                              folder_name=folder_name)
                with session_scope(self.account_id) as db_session:
                    common.update_metadata(self.account_id, folder.id, flags,
                                           db_session)
                    db_session.commit()
