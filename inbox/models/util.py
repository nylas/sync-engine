from collections import OrderedDict

from sqlalchemy import func

CHUNK_SIZE = 1000


def reconcile_message(new_message, session):
    """
    Check to see if the (synced) Message instance new_message was originally
    created/sent via the Inbox API (based on the X-Inbox-Uid header. If so,
    update the existing message with new attributes from the synced message
    and return it.

    """
    from inbox.models.message import Message

    if new_message.inbox_uid is None:
        return None

    if '-' not in new_message.inbox_uid:
        # Old X-Inbox-Id format; use the old reconciliation strategy.
        existing_message = session.query(Message).filter(
            Message.namespace_id == new_message.namespace_id,
            Message.inbox_uid == new_message.inbox_uid,
            Message.is_created == True).first()
        version = None
    else:
        # new_message has the new X-Inbox-Id format <public_id>-<version>
        # If this is an old version of a current draft, we want to:
        # * not commit a new, separate Message object for it
        # * not update the current draft with the old header values in the code
        #   below.
        expected_public_id, version = new_message.inbox_uid.split('-')
        existing_message = session.query(Message).filter(
            Message.namespace_id == new_message.namespace_id,
            Message.public_id == expected_public_id,
            Message.is_created == True).first()

    if existing_message is None:
        return None

    if version is None or int(version) == existing_message.version:
        existing_message.message_id_header = new_message.message_id_header
        existing_message.full_body = new_message.full_body
        existing_message.references = new_message.references

    return existing_message


def transaction_objects():
    """
    Return the mapping from API object name - which becomes the
    Transaction.object_type - for models that generate Transactions (i.e.
    models that implement the HasRevisions mixin).

    """
    from inbox.models import (Calendar, Contact, Message, Event, Block, Tag,
                              Thread)

    return {
        'calendar': Calendar,
        'contact': Contact,
        'draft': Message,
        'event': Event,
        'file': Block,
        'message': Message,
        'tag': Tag,
        'thread': Thread
    }


def delete_namespace(account_id, namespace_id):
    """
    Delete all the data associated with a namespace from the database.
    USE WITH CAUTION.

    """
    from inbox.models.session import session_scope
    from inbox.models import (Message, Block, Thread, Transaction, ActionLog,
                              Contact, Event, Account, Folder, Calendar, Tag,
                              Namespace)

    # Chunk delete for tables that might have a large concurrent write volume
    # to prevent those transactions from blocking.
    # NOTE: ImapFolderInfo does not fall into this category but we include it
    # here for simplicity.

    filters = OrderedDict()

    for cls in [Message, Block, Thread, Transaction, ActionLog, Contact,
                Event]:
        filters[cls] = cls.namespace_id == namespace_id

    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        if account.discriminator != 'easaccount':
            from inbox.models.backends.imap import (ImapUid,
                                                    ImapFolderSyncStatus,
                                                    ImapFolderInfo)
            filters[ImapUid] = ImapUid.account_id == account_id
            filters[ImapFolderSyncStatus] = \
                ImapFolderSyncStatus.account_id == account_id
            filters[ImapFolderInfo] = ImapFolderInfo.account_id == account_id
        else:
            from inbox.models.backends.eas import (EASUid, EASFolderSyncStatus)
            filters[EASUid] = EASUid.easaccount_id == account_id
            filters[EASFolderSyncStatus] = \
                EASFolderSyncStatus.account_id == account_id

    for cls in filters:
        with session_scope() as db_session:
            min_ = db_session.query(func.min(cls.id)).scalar()
            max_ = db_session.query(func.max(cls.id)).scalar()

        if not min_:
            continue

        for i in range(min_, max_, CHUNK_SIZE):
            # Set versioned=False since we do /not/ want Transaction records
            # created for these deletions.
            with session_scope(versioned=False) as db_session:
                db_session.query(cls).filter(
                    cls.id >= i, cls.id <= i + CHUNK_SIZE,
                    filters[cls]).delete(synchronize_session=False)
                db_session.commit()

    # Bulk delete for the other tables
    # NOTE: Namespace, Account are deleted at the end too.

    classes = [Folder, Calendar, Tag, Namespace, Account]
    for cls in classes:
        if cls in [Calendar, Tag]:
            filter_ = cls.namespace_id == namespace_id
        elif cls in [Folder]:
            filter_ = cls.account_id == account_id
        elif cls in [Namespace]:
            filter_ = cls.id == namespace_id
        elif cls in [Account]:
            filter_ = cls.id == account_id

        # Set versioned=False since we do /not/ want Transaction records
        # created for these deletions.
        with session_scope(versioned=False) as db_session:
            db_session.query(cls).filter(filter_).\
                delete(synchronize_session=False)
            db_session.commit()
