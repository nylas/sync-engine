#!/usr/bin/env python
# Duplicate categories were created because of an inadequate unique constraint
# in MySQL. This script deletes duplicate categories with no messages
# associated. If two or more duplicate categories exist with associated
# messages, they are consolidated into a single category and the other
# categories are deleted
import click

from itertools import chain
from inbox.ignition import engine_manager
from nylas.logging import get_logger, configure_logging
from inbox.models import MessageCategory, Category
from inbox.models.session import session_scope_by_shard_id

from sqlalchemy import func
from sqlalchemy.sql import exists, and_

configure_logging()
log = get_logger(purpose='duplicate-category-backfill')


def backfix_shard(shard_id, dry_run):
    categories_to_fix = []
    with session_scope_by_shard_id(shard_id) as db_session:
        # 'SELECT id FROM <table> GROUP BY <x>' does not select _all_ of the
        # ids in the group. MySQL chooses one id and returns it. The id chosen
        # is indeterminate. So we find the duplicate
        # (namespace_id, display_name, name) pairs and use them to query
        # for specific Category rows
        category_query = db_session.query(Category.namespace_id,
                                          Category.display_name,
                                          Category.name)

        duplicate_attrs = category_query. \
            group_by(Category.display_name,
                     Category.namespace_id,
                     Category.name).having(
                func.count(Category.id) > 1).all()

    for namespace_id, display_name, name in duplicate_attrs:
        duplicates = db_session.query(Category.id). \
            filter(Category.namespace_id == namespace_id,
                   Category.display_name == display_name,
                   Category.name == name).all()

        # duplicates is an array of tuples where each tuple is
        # (Category.id,). We flatten the tuples here so that each item in
        # categories_to_fix is a list of category ids that are duplicates
        categories_to_fix.append([item for item in chain(*duplicates)])

    categories_affected = 0
    categories_to_delete = []
    # Categories_to_fix is a list of tuples where each tuple
    # contains the duplicate categories
    for grouped_categories in categories_to_fix:
        # Keep track of categories with associated message categories
        categories_with_messages = []

        # It is possible for Messages to be associated with
        # more than one category. We choose the Category with
        # the lowest pk to be the "master" and all other duplicate
        # categories are deleted and their messages consolidated
        # into the master
        grouped_categories.sort()
        master_id = grouped_categories[0]
        categories_affected += len(grouped_categories)

        # Iterate over all of the duplicate categories except master
        for category_id in grouped_categories[1:]:
            with session_scope_by_shard_id(shard_id) as db_session:
                associated_messages = db_session.query(exists().where(
                    MessageCategory.category_id == category_id)).scalar()

                # if category has messages, they need to be de-duped
                # and consolidated
                if associated_messages:
                    log.info('Category has associated messages',
                             category_id=category_id)
                    categories_with_messages.append(category_id)

                # if category does not have messages, it can be deleted
                else:
                    categories_to_delete.append(category_id)
                    log.info('Category does not have associated messages',
                             category_id=category_id)

        if len(categories_with_messages) > 0:
            log.info('Consolidating messages into category',
                     category_id=master_id)

            for category_id in categories_with_messages:
                try:
                    with session_scope_by_shard_id(shard_id) as db_session:
                        messagecategories = db_session.query(MessageCategory).\
                                filter(MessageCategory.category_id == category_id).all()  # noqa

                        for mc in messagecategories:
                            # Its possible for a message to be associated with
                            # what we've declared to be the master category
                            # and the category we want to delete.
                            # MessageCategory has a unique constraint on
                            # (message_id, category_id) so we first query to
                            # see such an object exists. If it does, we
                            # point the MessageCategory to the master
                            # category. If it does not, then simply delete it
                            mc_exists = db_session.query(exists().where(and_(
                                MessageCategory.category_id == master_id,
                                MessageCategory.message_id == mc.message_id)))\
                                .scalar()

                            if not dry_run:
                                # If mc_exists == True, then there's a
                                # MessageCategory associated with the master
                                # and the current category, so we can delete
                                # the current category
                                if mc_exists:
                                    db_session.query(MessageCategory).filter_by(id=mc.id).delete()
                                else:
                                    # Master does not have a MessageCategory
                                    # for this message. Update this one to
                                    # point to the master
                                    mc.category_id = master_id
                                db_session.commit()

                            log.info('Updated MessageCategory', mc_id=mc.id,
                                     old_category_id=mc.category_id,
                                     new_category_id=master_id)

                    categories_to_delete.append(category_id)
                except Exception as e:
                    log.critical('Exception encountered while consolidating'
                                 ' messagecategories', e=str(e))
                    raise e

            # We REALLY don't want to delete the category we consolidated all
            # of the messagecategories into
            assert master_id not in categories_to_delete

        for category_id in categories_to_delete:
            if dry_run:
                log.info('Delete category', category_id=category_id)
                continue

            with session_scope_by_shard_id(shard_id) as db_session:
                db_session.query(Category).filter_by(id=category_id).delete()
                log.info('Deleted category', category_id=category_id)

            categories_to_delete.remove(category_id)

    log.info('Completed category migration on shard',
             categories_affected=categories_affected, shard_id=shard_id)


@click.command()
@click.option('--shard-id', type=int, default=None)
@click.option('--dry-run', is_flag=True)
def main(shard_id, dry_run):
    if shard_id is not None:
        backfix_shard(shard_id, dry_run)
    else:
        for shard_id in engine_manager.engines:
            backfix_shard(shard_id, dry_run)

if __name__ == '__main__':
    main()
