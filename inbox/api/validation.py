"""Utilities for validating user input to the API."""
from sqlalchemy.orm.exc import NoResultFound
from inbox.models import Tag, Thread, Block


class InputError(Exception):
    """Raised when but user input is processed."""
    pass


def validate_public_id(public_id):
    try:
        # raise ValueError on malformed public ids
        int(public_id, 36)
    except ValueError:
        raise InputError('Invalid id {}'.format(public_id))


def get_tags(tag_public_ids, namespace_id, db_session):
    tags = set()
    if tag_public_ids is None:
        return tags
    if not isinstance(tag_public_ids, list):
        raise InputError('{} is not a list of tag ids'.format(tag_public_ids))
    for public_id in tag_public_ids:
        validate_public_id(public_id)
        try:
            # We're trading a bit of performance for more meaningful error
            # messages here by looking these up one-by-one.
            tag = db_session.query(Tag). \
                filter(Tag.namespace_id == namespace_id,
                       Tag.public_id == public_id,
                       Tag.user_created == True).one()
            tags.add(tag)
        except NoResultFound:
            raise InputError('Invalid tag public id {}'.format(public_id))
    return tags


def get_attachments(block_public_ids, namespace_id, db_session):
    attachments = set()
    if block_public_ids is None:
        return attachments
    if not isinstance(block_public_ids, list):
        raise InputError('{} is not a list of block ids'.
                         format(block_public_ids))
    for public_id in block_public_ids:
        validate_public_id(public_id)
        try:
            block = db_session.query(Block). \
                filter(Block.public_id == public_id,
                       Block.namespace_id == namespace_id).one()
            # In the future we may consider discovering the filetype from the
            # data by using #magic.from_buffer(data, mime=True))
            attachments.add(block)
        except NoResultFound:
            raise InputError('Invalid block public id {}'.format(public_id))
    return attachments


def get_thread(thread_public_id, namespace_id, db_session):
    if thread_public_id is None:
        return None
    validate_public_id(thread_public_id)
    try:
        return db_session.query(Thread). \
            filter(Thread.public_id == thread_public_id,
                   Thread.namespace_id == namespace_id).one()
    except NoResultFound:
        raise InputError('Invalid thread public id {}'.
                         format(thread_public_id))
