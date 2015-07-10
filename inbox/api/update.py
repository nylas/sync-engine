from sqlalchemy.orm.exc import NoResultFound
from inbox.api.err import InputError
from inbox.models.action_log import schedule_action
from inbox.models import Category
# STOPSHIP(emfree): better naming/structure for this module

# TODO[k]: Instead of directly updating message.is_read, is_starred and
# .categories, call message.update_metadata() /after/ action is
# scheduled?


def update_message(message, request_data, db_session):
    accept_labels = message.namespace.account.provider == 'gmail'
    unread, starred, label_public_ids, folder_public_id = parse(
        request_data, accept_labels)
    update_message_flags(message, db_session, unread, starred)
    if label_public_ids is not None:
        update_message_labels(message, db_session, label_public_ids)
    elif folder_public_id is not None:
        update_message_folder(message, db_session, folder_public_id)


def update_thread(thread, request_data, db_session):
    accept_labels = thread.namespace.account.provider == 'gmail'
    # Backwards-compatibility shim
    added_tags = request_data.pop('add_tags', [])
    removed_tags = request_data.pop('remove_tags', [])

    unread, starred, label_public_ids, folder_public_id = parse(
        request_data, accept_labels)

    # -- Begin tags API shim
    if 'unread' in added_tags:
        unread = True
    elif 'unread' in removed_tags:
        unread = False

    if 'starred' in added_tags:
        starred = True
    elif 'starred' in removed_tags:
        starred = False

    if 'inbox' in removed_tags:
        if accept_labels:
            label_public_ids = [c.public_id for c in thread.categories]
            inbox_category = next(
                c for c in thread.categories if c.name == 'inbox')
            label_public_ids.remove(inbox_category.public_id)
        else:
            archive_category = db_session.query(Category).filter(
                Category.namespace_id == thread.namespace_id,
                Category.name == 'archive').first()
            folder_public_id = archive_category.public_id

    elif 'inbox' in added_tags:
        inbox_category = db_session.query(Category).filter(
            Category.namespace_id == thread.namespace_id,
            Category.name == 'inbox').first()
        if accept_labels:
            inbox_category = db_session.query(Category).filter(
                Category.namespace_id == thread.namespace_id,
                Category.name == 'inbox').first()
            label_public_ids = {c.public_id for c in thread.categories}
            label_public_ids.add(inbox_category.public_id)
            label_public_ids = list(label_public_ids)
        else:
            folder_public_id = inbox_category.public_id

    for message in thread.messages:
        if message.is_draft:
            continue
        update_message_flags(message, db_session, unread, starred)
        if label_public_ids is not None:
            update_message_labels(message, db_session, label_public_ids)
        elif folder_public_id is not None:
            update_message_folder(message, db_session, folder_public_id)

    # -- End tags API shim


def parse(request_data, accept_labels):
    unread = request_data.pop('unread', None)
    if unread is not None and not isinstance(unread, bool):
        raise InputError('"unread" must be true or false')

    starred = request_data.pop('starred', None)
    if starred is not None and not isinstance(starred, bool):
        raise InputError('"starred" must be true or false')

    label_public_ids = None
    folder_public_id = None

    if accept_labels:
        label_public_ids = request_data.pop('labels', None)
        if (label_public_ids is not None and
                not isinstance(label_public_ids, list)):
            raise InputError('"labels" must be a list of strings')
        if (label_public_ids is not None and
                not all(isinstance(l, basestring) for l in label_public_ids)):
            raise InputError('"labels" must be a list of strings')
        if request_data:
            raise InputError('Only the "unread", "starred" and "labels" '
                             'attributes can be changed')

    else:
        folder_public_id = request_data.pop('folder', None)
        if (folder_public_id is not None and
                not isinstance(folder_public_id, basestring)):
            raise InputError('"folder" must be a string')
        if request_data:
            raise InputError('Only the "unread", "starred" and "folder" '
                             'attributes can be changed')
    return (unread, starred, label_public_ids, folder_public_id)


def update_message_flags(message, db_session, unread=None, starred=None):
    if unread is not None and unread == message.is_read:
        message.is_read = not unread
        schedule_action('mark_unread', message, message.namespace_id,
                        db_session, unread=unread)

    if starred is not None and starred != message.is_starred:
        message.is_starred = starred
        schedule_action('mark_starred', message, message.namespace_id,
                        db_session, starred=starred)


def update_message_labels(message, db_session, label_public_ids):
    categories = set()
    for id_ in label_public_ids:
        try:
            category = db_session.query(Category).filter(
                Category.namespace_id == message.namespace_id,
                Category.public_id == id_).one()
            categories.add(category)
        except NoResultFound:
            raise InputError(u'Label {} does not exist'.format(id_))

    added_categories = categories - set(message.categories)
    removed_categories = set(message.categories) - categories

    added_labels = []
    removed_labels = []
    special_label_map = {
        'inbox': '\\Inbox',
        'important': '\\Important',
        'all': '\\All',  # STOPSHIP(emfree): verify
        'trash': '\\Trash',
        'spam': '\\Spam'
    }
    for category in added_categories:
        if category.name in special_label_map:
            added_labels.append(special_label_map[category.name])
        elif category.name in ('drafts', 'sent'):
            raise InputError('The "{}" label cannot be changed'.
                             format(category.name))
        else:
            added_labels.append(category.display_name)

    for category in removed_categories:
        if category.name in special_label_map:
            removed_labels.append(special_label_map[category.name])
        elif category.name in ('drafts', 'sent'):
            raise InputError('The "{}" label cannot be changed'.
                             format(category.name))
        else:
            removed_labels.append(category.display_name)

    # Optimistically update message state.
    message.categories = categories
    if removed_labels or added_labels:
        schedule_action('change_labels', message, message.namespace_id,
                        removed_labels=removed_labels,
                        added_labels=added_labels,
                        db_session=db_session)


def update_message_folder(message, db_session, folder_public_id):
    try:
        category = db_session.query(Category).filter(
            Category.namespace_id == message.namespace_id,
            Category.public_id == folder_public_id).one()
    except NoResultFound:
        raise InputError(u'Folder {} does not exist'.
                         format(folder_public_id))

    # STOPSHIP(emfree): what about sent/inbox duality?
    if category not in message.categories:
        message.categories = [category]
        schedule_action('move', message, message.namespace_id, db_session,
                        destination=category.display_name)
