from sqlalchemy.orm.exc import NoResultFound

from nylas.logging import get_logger
log = get_logger()
from inbox.models import Category
from inbox.models.action_log import schedule_action
from inbox.api.validation import valid_public_id
from inbox.api.err import InputError
# STOPSHIP(emfree): better naming/structure for this module


def update_message(message, request_data, db_session, optimistic):
    accept_labels = message.namespace.account.provider == 'gmail'
    # Update flags (message.{is_read, is_starred})
    unread, starred = parse_flags(request_data)
    update_message_flags(message, db_session, optimistic, unread, starred)
    # Update folders/ labels (message.categories)
    if accept_labels:
        labels = parse_labels(request_data, db_session, message.namespace_id)
        if labels is not None:
            added_labels = labels - set(message.categories)
            removed_labels = set(message.categories) - labels
            update_message_labels(message, db_session, added_labels,
                                  removed_labels, optimistic)
    else:
        folder = parse_folder(request_data, db_session, message.namespace_id)
        if folder is not None:
            update_message_folder(message, db_session, folder,
                                  optimistic)


def update_thread(thread, request_data, db_session, optimistic):
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
                                          removed_labels, optimistic)

    elif folder is not None:
        for message in thread.messages:
            # Exclude drafts and sent messages from thread-level moves.
            if (not message.is_draft and not message.is_sent and
                    'sent' not in {c.name for c in message.categories}):
                update_message_folder(message, db_session, folder,
                                      optimistic)

    for message in thread.messages:
        if not message.is_draft:
            update_message_flags(message, db_session, optimistic, unread,
                                 starred)

## FLAG UPDATES ##


def parse_flags(request_data):
    unread = request_data.pop('unread', None)
    if unread is not None and not isinstance(unread, bool):
        raise InputError('"unread" must be true or false')

    starred = request_data.pop('starred', None)
    if starred is not None and not isinstance(starred, bool):
        raise InputError('"starred" must be true or false')
    return unread, starred


def update_message_flags(message, db_session, optimistic, unread=None,
                         starred=None):
    if unread is not None and unread == message.is_read:
        if optimistic:
            message.is_read = not unread

        schedule_action('mark_unread', message, message.namespace_id,
                        db_session, unread=unread)

    if starred is not None and starred != message.is_starred:
        if optimistic:
            message.is_starred = starred

        schedule_action('mark_starred', message, message.namespace_id,
                        db_session, starred=starred)

## FOLDER UPDATES ##


def parse_folder(request_data, db_session, namespace_id):
    # TODO deprecate being able to post "folder" and not "folder_id"
    if 'folder_id' not in request_data and 'folder' not in request_data:
        return
    folder_public_id = request_data.pop('folder_id', None) or \
        request_data.pop('folder', None)
    if folder_public_id is None:
        # One of 'folder_id'/ 'folder' was present AND set to None.
        # Not allowed.
        raise InputError('Removing all folders is not allowed.')

    valid_public_id(folder_public_id)
    try:
        return db_session.query(Category). \
            filter(Category.namespace_id == namespace_id,
                   Category.public_id == folder_public_id).one()
    except NoResultFound:
        raise InputError(u'The folder {} does not exist'.
                         format(folder_public_id))


def update_message_folder(message, db_session, category, optimistic):
    # STOPSHIP(emfree): what about sent/inbox duality?
    if category not in message.categories:
        if optimistic:
            message.categories = [category]
            message.categories_changes = True

        schedule_action('move', message, message.namespace_id, db_session,
                        destination=category.display_name)

### LABEL UPDATES ###


def parse_labels(request_data, db_session, namespace_id):
    # TODO deprecate being able to post "labels" and not "label_ids"
    if 'label_ids' not in request_data and 'labels' not in request_data:
        return

    label_public_ids = request_data.pop('label_ids', []) or \
        request_data.pop('labels', [])

    if not label_public_ids:
        # One of 'label_ids'/ 'labels' was present AND set to [].
        # Not allowed.
        raise InputError('Removing all labels is not allowed.')

    # TODO(emfree): Use a real JSON schema validator for this sort of thing.
    if not isinstance(label_public_ids, list):
        raise InputError('"labels" must be a list')

    for id_ in label_public_ids:
        valid_public_id(id_)

    labels = set()
    for id_ in label_public_ids:
        try:
            category = db_session.query(Category).filter(
                Category.namespace_id == namespace_id,
                Category.public_id == id_).one()
            labels.add(category)
        except NoResultFound:
            raise InputError(u'The label {} does not exist'.format(id_))
    return labels


def update_message_labels(message, db_session, added_categories,
                          removed_categories, optimistic):
    special_label_map = {
        'inbox': '\\Inbox',
        'important': '\\Important',
        'all': '\\All',  # STOPSHIP(emfree): verify
        'trash': '\\Trash',
        'spam': '\\Spam'
    }

    validate_labels(db_session, added_categories, removed_categories)

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

    if optimistic:
        # Optimistically update message state,
        # in a manner consistent with Gmail.
        for cat in added_categories:
            message.categories.add(cat)

        for cat in removed_categories:
            # Removing '\\All'/ \\Trash'/ '\\Spam' does not do anything on Gmail
            # i.e. does not move the message to a different folder, so don't
            # discard the corresponding category yet.
            # If one of these has been *added* too, apply_gmail_label_rules()
            # will do the right thing to ensure mutual exclusion.
            if cat.name not in ('all', 'trash', 'spam'):
                message.categories.discard(cat)

        apply_gmail_label_rules(db_session, message, added_categories, removed_categories)

        if removed_labels or added_labels:
            message.categories_changes = True

    if removed_labels or added_labels:
        schedule_action('change_labels', message, message.namespace_id,
                        removed_labels=removed_labels,
                        added_labels=added_labels,
                        db_session=db_session)


def validate_labels(db_session, added_categories, removed_categories):
    """
    Validate that the labels added and removed obey Gmail's semantics --
    Gmail messages MUST belong to exactly ONE of the '[Gmail]All Mail',
    '[Gmail]Trash', '[Gmail]Spam' folders.

    """
    add = {c.name for c in added_categories if c.name}
    add_all = ('all' in add)
    add_trash = ('trash' in add)
    add_spam = ('spam' in add)

    if (add_all and (add_trash or add_spam)) or (add_trash and add_spam):
        raise InputError('Only one of "all", "trash" or "spam" can be added')

    remove = {c.name for c in removed_categories if c.name}
    remove_all = ('all' in remove)
    remove_trash = ('trash' in remove)
    remove_spam = ('spam' in remove)

    if (remove_all and remove_trash and remove_spam):
        raise InputError('"all", "trash" and "spam" cannot all be removed')


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
    add = {}
    discard = {}

    categories = {c.name: c for c in message.categories if c.name}

    for cat in added_categories:
        if cat.name == 'all':
            # Adding the 'all' label should remove the 'trash'/'spam' and
            # preserve all else.
            discard = {'trash', 'spam'}
        elif cat.name == 'trash':
            # Adding the 'trash' label should remove the 'all'/'spam' and 'inbox',
            # and preserve all else.
            discard = {'all', 'spam', 'inbox'}
        elif cat.name == 'spam':
            # Adding the 'spam' label should remove the 'all'/'trash' and 'inbox',
            # and preserve all else.
            discard = {'all', 'trash', 'inbox'}
        elif cat.name == 'inbox':
            # Adding the 'inbox' label should remove the 'trash'/ 'spam',
            # adding 'all' if needed, and preserve all else.
            add = {'all'}
            discard = {'trash', 'spam'}
        # Adding any other label does not change the associated folder
        # so nothing additional needs to be done.

    for name in add:
        if name not in categories:
            category = db_session.query(Category).filter(
                Category.namespace_id == message.namespace_id,
                Category.name == name).one()
            message.categories.add(category)

    for name in discard:
        if name in categories:
            message.categories.discard(categories[name])

    # Nothing needs to be done for the removed_categories:
    # 1. Removing '\\All'/ \\Trash'/ '\\Spam' does not do anything on Gmail i.e.
    # does not move the message to a different folder so these are not removed
    # via `removed_categories` either; the logic above for `added_categories`
    # ensures there is only one present however.
    # 2. Removing '\\Inbox'/ '\\Important'/ custom labels simply removes these
    # labels and does not move the message between folders.
