# TODO[k]: participants as nested, tags too.
# first/last_message_timestamp as {'type': 'date', 'format': 'dateOptionalTime'}
# for range filters and such?
THREAD_MAPPING = {
    'properties': {
        'namespace_id': {'type': 'string'},
        'tags': {'type': 'string'},
        'last_message_timestamp': {'type': 'date', 'format': 'dateOptionalTime'},
        'object': {'type': 'string'},
        'message_ids': {'type': 'string'},
        'snippet': {'type': 'string'},
        'participants': {'type': 'string'},
        'first_message_timestamp': {'type': 'date', 'format': 'dateOptionalTime'},
        'id': {'type': 'string'},
        'subject': {'type': 'string'}
    }
}

# TODO[k]:
# from, to, cc, bcc as nested.
# date as {'type': 'date', 'format': 'dateOptionalTime'} for range filters and such?
MESSAGE_MAPPING = {
    '_parent': {
        'type': 'thread'
    },
    'properties': {
        'id': {'type': 'string'},
        'object': {'type': 'string'},
        'namespace_id': {'type': 'string'},
        'subject': {'type': 'string'},
        'from': {'type': 'string'},
        'to': {'type': 'string'},
        'cc': {'type': 'string'},
        'bcc': {'type': 'string'},
        'date': {'type': 'date', 'format': 'dateOptionalTime'},
        'thread_id': {'type': 'string'},
        'snippet': {'type': 'string'},
        'body': {'type': 'string'},
        'unread': {'type': 'boolean'},
        'files': {'type': 'nested', 'properties': {'size': {'type': 'long'}, 'id': {'type': 'string'}, 'content_type': {'type': 'string'}, 'filename': {'type': 'string'}}},
    }
}

# TODO[k]: message._parent = thread
NAMESPACE_INDEX_MAPPING = {
    'thread': THREAD_MAPPING,
    'message': MESSAGE_MAPPING
}
