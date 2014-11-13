THREAD_MAPPING = {
    'properties': {
        'namespace_id': {'type': 'string'},
        'tags': {'type': 'nested', 'properties': {'id': {'type': 'string'}, 'name': {'type': 'string'}}},
        'last_message_timestamp': {'type': 'date', 'format': 'dateOptionalTime'},
        'object': {'type': 'string'},
        'message_ids': {'type': 'string'},
        'snippet': {'type': 'string'},
        'participants': {'type': 'nested', 'properties': {'email': {'type': 'string'}, 'name': {'type': 'string'}}},
        'first_message_timestamp': {'type': 'date', 'format': 'dateOptionalTime'},
        'id': {'type': 'string'},
        'subject': {'type': 'string'}
    }
}

MESSAGE_MAPPING = {
    '_parent': {
        'type': 'thread'
    },
    'properties': {
        'id': {'type': 'string'},
        'object': {'type': 'string'},
        'namespace_id': {'type': 'string'},
        'subject': {'type': 'string'},
        'from': {'type': 'nested', 'properties': {'email': {'type': 'string'}, 'name': {'type': 'string'}}},
        'to': {'type': 'nested', 'properties': {'email': {'type': 'string'}, 'name': {'type': 'string'}}},
        'cc': {'type': 'nested', 'properties': {'email': {'type': 'string'}, 'name': {'type': 'string'}}},
        'bcc': {'type': 'nested', 'properties': {'email': {'type': 'string'}, 'name': {'type': 'string'}}},
        'date': {'type': 'date', 'format': 'dateOptionalTime'},
        'thread_id': {'type': 'string'},
        'snippet': {'type': 'string'},
        'body': {'type': 'string'},
        'unread': {'type': 'boolean'},
        'files': {'type': 'nested', 'properties': {'size': {'type': 'long'}, 'id': {'type': 'string'}, 'content_type': {'type': 'string'}, 'filename': {'type': 'string'}}},
    }
}

NAMESPACE_INDEX_MAPPING = {
    'thread': THREAD_MAPPING,
    'message': MESSAGE_MAPPING
}
