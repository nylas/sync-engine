"""migrate data for folders overhaul

Revision ID: 334b33f18b4f
Revises: 23e204cd1d91
Create Date: 2015-07-09 00:23:04.918833

"""

# revision identifiers, used by Alembic.
revision = '334b33f18b4f'
down_revision = '23e204cd1d91'

from sqlalchemy import asc
from sqlalchemy.orm import joinedload, subqueryload, load_only
from inbox.log import configure_logging, get_logger
configure_logging()
log = get_logger()


def populate_labels(uid, account, db_session):
    from inbox.models import Label
    existing_labels = {
        (l.name, l.canonical_name): l for l in account.labels
    }
    uid.is_draft = '\\Draft' in uid.g_labels
    uid.is_starred = '\\Starred' in uid.g_labels

    category_map = {
        '\\Inbox': 'inbox',
        '\\Important': 'important',
        '\\Sent': 'sent'
    }

    remote_labels = set()
    for label_string in uid.g_labels:
        if label_string in ('\\Draft', '\\Starred'):
            continue
        elif label_string in category_map:
            remote_labels.add((category_map[label_string],
                               category_map[label_string]))
        else:
            remote_labels.add((label_string, None))

    for key in remote_labels:
        if key not in existing_labels:
            label = Label.find_or_create(db_session, account, key[0], key[1])
            uid.labels.add(label)
            account.labels.append(label)
        else:
            uid.labels.add(existing_labels[key])


def set_labels_for_imapuids(account, db_session):
    from inbox.models.backends.imap import ImapUid
    uids = db_session.query(ImapUid).filter(
        ImapUid.account_id == account.id).options(
            subqueryload(ImapUid.labelitems).joinedload('label'))
    for uid in uids:
        populate_labels(uid, account, db_session)
        log.info('Updated UID labels', account_id=account.id, uid=uid.id)


def create_categories_for_folders(account, db_session):
    from inbox.models import Folder, Category
    for folder in db_session.query(Folder).filter(
            Folder.account_id == account.id):
        cat = Category.find_or_create(
            db_session, namespace_id=account.namespace.id,
            name=folder.canonical_name, display_name=folder.name,
            type_='folder')
        folder.category = cat
    db_session.commit()


def create_categories_for_easfoldersyncstatuses(account, db_session):
    from inbox.mailsync.backends.eas.base.foldersync import save_categories
    save_categories(db_session, account, account.primary_device_id)
    db_session.commit()
    save_categories(db_session, account, account.secondary_device_id)


def migrate_account_metadata(account_id):
    from inbox.models.session import session_scope
    from inbox.models import Account
    with session_scope(versioned=False) as db_session:
        account = db_session.query(Account).get(account_id)
        if account.discriminator == 'easaccount':
            create_categories_for_easfoldersyncstatuses(account, db_session)
        else:
            create_categories_for_folders(account, db_session)
        if account.discriminator == 'gmailaccount':
            set_labels_for_imapuids(account, db_session)
        db_session.commit()


def migrate_messages(account_id):
    from inbox.models.session import session_scope
    from inbox.models import Message, Namespace
    with session_scope(versioned=False) as db_session:
        namespace = db_session.query(Namespace).filter_by(
            account_id=account_id).one()
        offset = 0
        while True:
            messages = db_session.query(Message). \
                filter(Message.namespace_id == namespace.id). \
                options(load_only(Message.id, Message.is_read,
                                  Message.is_starred, Message.is_draft),
                        joinedload(Message.namespace).load_only('id'),
                        subqueryload(Message.imapuids),
                        subqueryload(Message.easuids),
                        subqueryload(Message.messagecategories)). \
                with_hint(Message, 'USE INDEX (ix_message_namespace_id)'). \
                order_by(asc(Message.id)).limit(1000).offset(offset).all()
            if not messages:
                return
            for message in messages:
                try:
                    message.update_metadata(message.is_draft)
                except IndexError:
                    # Can happen for messages without a folder.
                    pass
                log.info('Updated message', namespace_id=namespace.id,
                         message_id=message.id)
            db_session.commit()
            offset += 1000


def migrate_account(account_id):
    migrate_account_metadata(account_id)
    migrate_messages(account_id)


def upgrade():
    from inbox.models.session import session_scope
    from inbox.models import Account
    with session_scope() as db_session:
        account_ids = [id_ for id_, in db_session.query(Account.id)]

    for id_ in account_ids:
        migrate_account(id_)


def downgrade():
    pass
