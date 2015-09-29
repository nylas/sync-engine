import time
import math
from collections import OrderedDict

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
    from inbox.models import (Calendar, Contact, Message, Event, Block,
                              Category, Thread, Account)

    return {
        'calendar': Calendar,
        'contact': Contact,
        'draft': Message,
        'event': Event,
        'file': Block,
        'message': Message,
        'thread': Thread,
        'label': Category,
        'folder': Category,
        'account': Account
    }


def delete_namespace(account_id, namespace_id, dry_run=False):
    """
    Delete all the data associated with a namespace from the database.
    USE WITH CAUTION.

    NOTE: This function is only called from bin/delete-account-data.
    It prints to stdout.

    """
    from inbox.models.session import session_scope
    from inbox.models import Account
    from inbox.ignition import main_engine

    # Bypass the ORM for performant bulk deletion;
    # we do /not/ want Transaction records created for these deletions,
    # so this is okay.
    engine = main_engine()

    # Chunk delete for tables that might have a large concurrent write volume
    # to prevent those transactions from blocking.
    # NOTE: ImapFolderInfo does not fall into this category but we include it
    # here for simplicity.

    filters = OrderedDict()

    for table in ['message', 'block', 'thread', 'transaction', 'actionlog',
                  'contact', 'event', 'dataprocessingcache']:
        filters[table] = ('namespace_id', namespace_id)

    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        if account.discriminator != 'easaccount':
            filters['imapuid'] = ('account_id', account_id)
            filters['imapfoldersyncstatus'] = ('account_id', account_id)
            filters['imapfolderinfo'] = ('account_id', account_id)
        else:
            filters['easuid'] = ('easaccount_id', account_id)
            filters['easfoldersyncstatus'] = ('account_id', account_id)

    for cls in filters:
        _batch_delete(engine, cls, filters[cls], dry_run=dry_run)

    # Use a single delete for the other tables. Rows from tables which contain
    # cascade-deleted foreign keys to other tables deleted here (or above)
    # are also not always explicitly deleted, except where needed for
    # performance.
    #
    # NOTE: Namespace, Account are deleted at the end too.

    query = 'DELETE FROM {} WHERE {}={};'

    filters = OrderedDict()
    for table in ('category', 'calendar'):
        filters[table] = ('namespace_id', namespace_id)
    for table in ('folder', 'label'):
        filters[table] = ('account_id', account_id)
    filters['namespace'] = ('id', namespace_id)

    for table, (column, id_) in filters.iteritems():
        print 'Performing bulk deletion for table: {}'.format(table)
        start = time.time()

        if not dry_run:
            engine.execute(query.format(table, column, id_))
        else:
            print query.format(table, column, id_)

        end = time.time()
        print 'Completed bulk deletion for table: {}, time taken: {}'.\
            format(table, end - start)

    # Delete the account object manually to get rid of the various objects
    # associated with it (e.g: secrets, tokens, etc.)
    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        if dry_run is False:
            db_session.delete(account)
            db_session.commit()


def _batch_delete(engine, table, (column, id_), dry_run=False):
    count = engine.execute(
        'SELECT COUNT(*) FROM {} WHERE {}={};'.format(table, column, id_)).\
        scalar()

    if count == 0:
        print 'Completed batch deletion for table: {}'.format(table)
        return

    batches = int(math.ceil(float(count) / CHUNK_SIZE))

    print 'Starting batch deletion for table: {}, rows: {} number of batches: {}'.\
          format(table, count, batches)
    start = time.time()

    query = 'DELETE FROM {} WHERE {}={} LIMIT 1000;'.format(table, column, id_)

    for i in range(0, batches):
        print query
        if dry_run is False:
            engine.execute(query)

    end = time.time()
    print 'Completed batch deletion for table: {}, time taken: {}'.\
        format(table, end - start)
