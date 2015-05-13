import pytest

from inbox.models import Message, Thread
from inbox.search.adaptor import (NamespaceSearchEngine, SearchEngineError,
                                  new_connection)
from inbox.search.mappings import THREAD_MAPPING, MESSAGE_MAPPING
from inbox.search.util import index_messages, index_threads, delete_index


def test_index_creation(db, default_namespace):
    namespace_id = default_namespace.id
    namespace_public_id = default_namespace.public_id

    # Test number of indices
    message_indices = index_messages(namespace_id, namespace_public_id)
    message_count = db.session.query(Message).filter(
        Message.namespace_id == namespace_id).count()

    thread_indices = index_threads(namespace_id, namespace_public_id)
    thread_count = db.session.query(Thread).filter(
        Thread.namespace_id == namespace_id).count()

    assert message_indices == message_count and thread_indices == thread_count

    # Test index mappings
    search_engine = NamespaceSearchEngine(default_namespace.public_id,
                                          create_index=False)

    thread_mapping = search_engine.threads.get_mapping()
    assert thread_mapping[namespace_public_id]['mappings']['thread']['properties'] == \
        THREAD_MAPPING['properties']

    message_mapping = search_engine.messages.get_mapping()
    assert all(item in message_mapping[namespace_public_id]['mappings']['message']['properties']
               for item in MESSAGE_MAPPING['properties'])


def test_index_deletion(db, default_namespace):
    namespace_id = default_namespace.id
    namespace_public_id = default_namespace.public_id

    # Indirectly creates index
    thread_indices = index_threads(namespace_id, namespace_public_id)
    thread_count = db.session.query(Thread).filter(
        Thread.namespace_id == namespace_id).count()
    assert thread_indices == thread_count

    delete_index(namespace_id, namespace_public_id)

    # Test index deletion
    client = new_connection()
    assert client.indices.exists([namespace_public_id]) is False

    # Test non-existent index deletion does /not/ raise exception
    delete_index(namespace_id, 'Non-existent index')
