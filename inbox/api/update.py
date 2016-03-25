from sqlalchemy.orm.exc import NoResultFound

from nylas.logging import get_logger
log = get_logger()
from inbox.models import Category
from inbox.models.action_log import schedule_action
from inbox.api.validation import valid_public_id
from inbox.api.err import InputError
# STOPSHIP(emfree): better naming/structure for this module

# TODO[k]: Instead of directly updating message.is_read, is_starred and
# .categories, call message.update_metadata() /after/ action is
# scheduled?


def update_message(message, request_data, db_session):
    accept_labels = message.namespace.account.provider == 'gmail'
    unread, starred = parse_flags(request_data)
    update_message_flags(message, db_session, unread, starred)
    if accept_labels:
        labels = parse_labels(request_data, db_session, message.namespace_id)
        if labels is not None:
            added_labels = labels - set(message.categories)
            removed_labels = set(message.categories) - labels
            update_message_labels(message, db_session, added_labels,
                                  removed_labels)
    else:
        folder = parse_folder(request_data, db_session, message.namespace_id)
        if folder is not None:
            update_message_folder(message, db_session, folder)


def update_thread(thread, request_data, db_session):
    accept_labels = thread.namespace.account.provider == 'gmail'

    unread, starred, = parse_flags(request_data)
    if accept_labels:
        labels = parse_labels(request_data, db_session, thread.namespace_id)
    else:
        folder = parse_folder(request_data, db_session, thread.namespace_id)
    if request_data:
        raise InputError(u'Unexpected attribute: {}'.
                         format(request_data.keys()[0]))

    if accept_labels:
        if labels is not None:
            new_labels = labels - set(thread.categories)
            removed_labels = set(thread.categories) - labels

            for message in thread.messages:
                if not message.is_draft:
                    update_message_labels(message, db_session, new_labels,
                                          removed_labels)

    elif folder is not None:
        for message in thread.messages:
            # Exclude drafts and sent messages from thread-level moves.
            if (not message.is_draft and not message.is_sent and
                    'sent' not in {c.name for c in message.categories}):
                update_message_folder(message, db_session, folder)

    for message in thread.messages:
        if not message.is_draft:
            update_message_flags(message, db_session, unread, starred)


def parse_flags(request_data):
    unread = request_data.pop('unread', None)
    if unread is not None and not isinstance(unread, bool):
        raise InputError('"unread" must be true or false')

    starred = request_data.pop('starred', None)
    if starred is not None and not isinstance(starred, bool):
        raise InputError('"starred" must be true or false')
    return unread, starred


def parse_labels(request_data, db_session, namespace_id):
    # TODO deprecate being able to post "labels" and not "label_ids"
    label_public_ids = request_data.pop('label_ids', None) or \
        request_data.pop('labels', None)
    if label_public_ids is None:
        return
    # TODO(emfree): Use a real JSON schema validator for this sort of thing.
    if not isinstance(label_public_ids, list):
        raise InputError('"labels" must be a list')
    for id_ in label_public_ids:
        valid_public_id(id_)

    labels = set()
    for id_ in label_public_ids:
        try:
            cat = db_session.query(Category).filter(
                Category.namespace_id == namespace_id,
                Category.public_id == id_).one()
            labels.add(cat)
        except NoResultFound:
            raise InputError(u'The label {} does not exist'.format(id_))
    return labels


def parse_folder(request_data, db_session, namespace_id):
    # TODO deprecate being able to post "folder" and not "folder_id"
    folder_public_id = request_data.pop('folder_id', None) or \
        request_data.pop('folder', None)
    if folder_public_id is None:
        return
    valid_public_id(folder_public_id)
    try:
        return db_session.query(Category). \
            filter(Category.namespace_id == namespace_id,
                   Category.public_id == folder_public_id).one()
    except NoResultFound:
        raise InputError(u'The folder {} does not exist'.
                         format(folder_public_id))


def update_message_flags(message, db_session, unread=None, starred=None):
    if unread is not None and unread == message.is_read:
        message.is_read = not unread
        schedule_action('mark_unread', message, message.namespace_id,
                        db_session, unread=unread)

    if starred is not None and starred != message.is_starred:
        message.is_starred = starred
        schedule_action('mark_starred', message, message.namespace_id,
                        db_session, starred=starred)


def update_message_labels(message, db_session, added_categories,
                          removed_categories):
    special_label_map = {
        'inbox': '\\Inbox',
        'important': '\\Important',
        'all': '\\All',  # STOPSHIP(emfree): verify
        'trash': '\\Trash',
        'spam': '\\Spam'
    }

    added_labels = []
    removed_labels = []
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

    # Optimistically update message state,
    # in a manner that is consistent with Gmail.
    for cat in added_categories:
        message.categories.add(cat)
    for cat in removed_categories:
        message.categories.discard(cat)
    apply_gmail_label_rules(db_session, message, added_categories, removed_categories)

    if removed_labels or added_labels:
        message.categories_changes = True
        schedule_action('change_labels', message, message.namespace_id,
                        removed_labels=removed_labels,
                        added_labels=added_labels,
                        db_session=db_session)


def apply_gmail_label_rules(db_session, message, added_categories, removed_categories):
    """
    The API optimistically updates `message.categories` so ensure it does so
    in a manner consistent with Gmail, namely:

    1. Adding one of 'all', 'trash', 'spam' removes the other two --
    a message MUST belong to exactly ONE of the '[Gmail]All Mail', '[Gmail]Trash',
    '[Gmail]Spam' folders.

    2. '\\Inbox' is a special label as well --
    adding it removes a message out of the '[Gmail]Trash'/ '[Gmail]Spam' folders
    and into the '[Gmail]All Mail' folder.

    """
    add = ()
    discard = ()

    categories = {c.name: c for c in message.categories if c.name}

    for cat in added_categories:
        if cat.name == 'all':
            # Adding the 'all' label should remove the 'trash'/'spam' and
            # preserve all else.
            discard = ('trash', 'spam')
        elif cat.name == 'trash':
            # Adding the 'trash' label should remove the 'all'/'spam' and 'inbox',
            # and preserve all else.
            discard = ('all', 'spam', 'inbox')
        elif cat.name == 'spam':
            # Adding the 'spam' label should remove the 'all'/'trash' and 'inbox',
            # and preserve all else.
            discard = ('all', 'trash', 'inbox')
        elif cat.name == 'inbox':
            # Adding the 'inbox' label should remove the 'trash'/ 'spam',
            # adding 'all' if needed, and preserve all else.
            add = ('all')
            discard = ('trash', 'spam')
        # Adding any other label does not change the associated folder
        # so nothing additional needs to be done.

    for name in add:
        if name not in message.categories:
            category = db_session.query(Category).filter(
                Category.namespace_id == message.namespace_id,
                Category.name == name).one()
            message.categories.add(category)

    for name in discard:
        if name in categories:
            message.categories.discard(categories[name])

    # Nothing needs to be done for the removed_categories:
    # 1. Removing '\\All'/ \\Trash'/ '\\Spam' does not do anything on Gmail i.e.
    # does not move the message to a different folder,
    # 2. Removing '\\Inbox'/ '\\Important'/ custom labels simply removes these
    # labels as well and does not move the message between folders.

    # Validate labels:
    # verify the message's labels operations make sense with respect to
    # Gmail's semantics.
    categories = {c.name for c in message.categories}
    has_all = ('all' in categories)
    has_trash = ('trash' in categories)
    has_spam = ('spam' in categories)
    if (has_all and (has_trash or has_spam) or (has_trash and has_spam) or
            not any([has_all, has_trash, has_trash])):
        log.error('Invalid labels', namespace_id=message.namespace_id,
                  message_id=message.id,
                  message_categories=[(c.name, c.display_name) for c
                                      in message.categories],
                  added_categories=[(c.name, c.display_name) for c
                                    in added_categories],
                  removed_categories=[(c.name, c.display_name) for c
                                      in removed_categories])


def update_message_folder(message, db_session, category):
    # STOPSHIP(emfree): what about sent/inbox duality?
    if category not in message.categories:
        message.categories = [category]
        message.categories_changes = True
        schedule_action('move', message, message.namespace_id, db_session,
                        destination=category.display_name)
