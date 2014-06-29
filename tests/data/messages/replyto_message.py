from flanker import mime


# Email from the sync dump exported to the 'test' db
with open('tests/data/messages/replyto_message.txt', 'r') as f:
    message = f.read()

parsed = mime.from_string(message)

message_id = parsed.headers.get('Message-ID')
references = parsed.headers.get('References')

TEST_MSG = {
    'message-id': message_id,
    'references': references
}
